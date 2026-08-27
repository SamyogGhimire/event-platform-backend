# DEBUGGING.md

Authentic failure records from live chaos experiments against PostgreSQL.
Scripts live in `chaos/`; raw logs in `chaos/artifacts/`.

---

## Issue 1 — Race conditions under parallel enrollment (overbooking)

### Symptom

With `capacity=1`, five seekers enrolled simultaneously. After the race settled, the
database held **5 active `ENROLLED` rows** for a single event.

Captured from `chaos/artifacts/chaos_a_overbooking.log` (2026-08-27):

```text
Created event id=4 capacity=1
[THREAD OK] seeker_id=11 enrollment_id=1
[THREAD OK] seeker_id=10 enrollment_id=3
[THREAD OK] seeker_id=12 enrollment_id=2
[THREAD OK] seeker_id=8 enrollment_id=4
[THREAD OK] seeker_id=9 enrollment_id=5
FINAL active ENROLLED count = 5 (capacity was 1)
*** OVERBOOKING CONFIRMED — race condition reproduced ***
```

### Diagnosis

Reproduced with `python chaos/chaos_a_concurrency.py`, which uses a deliberately
broken enroll path:

```python
event = Event.objects.get(pk=event_id)  # NO select_for_update()
enrolled_count = Enrollment.objects.filter(...ENROLLED).count()
time.sleep(0.05)  # widen the race window
if enrolled_count >= event.capacity:
    raise RuntimeError("capacity_full")
Enrollment.objects.create(...)
```

All five threads read `enrolled_count=0` before any insert committed, then all
five inserted.

### Root Cause

Classic **check-then-act** race. A non-locking `COUNT(*)` + later `INSERT` is not
atomic under `READ COMMITTED`. Concurrent transactions each observe a stale count
and overbook.

`TransactionTestCase` / threaded clients also exposed connection-handling issues:
each worker thread must call `connections.close_all()` so Django does not share a
connection across threads.

### Fix

Pessimistic locking on the event row:

```python
with transaction.atomic():
    event = Event.objects.select_for_update().get(pk=event_id)
    enrolled_count = Enrollment.objects.filter(
        event=event, status=Enrollment.Status.ENROLLED
    ).count()
    if event.capacity is not None and enrolled_count >= event.capacity:
        raise APIError(detail="Event capacity full.", code="capacity_full")
    Enrollment.objects.create(...)
```

Implemented in `events/services.py::enroll_seeker`.

### Verification

```bash
python manage.py test events.tests.test_concurrency -v 2
```

Result (2026-08-27):

```text
test_capacity_one_five_parallel_seekers ... ok
test_parallel_enrollment_never_exceeds_capacity ... ok
# capacity=10 with 9 prefilled + 5 racers → exactly 10 ENROLLED, 4× capacity_full
```

---

## Issue 2 — Partial unique index DDL syntax + naive `unique_together` blocking re-enrollment

### Symptom A — IntegrityError on cancel → re-enroll

With a naive `UNIQUE (event_id, seeker_id)` (no status predicate), the lifecycle
**Enroll → Cancel → Re-enroll** crashed:

```text
STEP 1 ENROLLED enrollment_id=9 status=ENROLLED
STEP 2 CANCELLED enrollment_id=9 status=CANCELLED
STEP 3 RE-ENROLL — inserting new ENROLLED row…
django.db.utils.IntegrityError: duplicate key value violates unique constraint
  "chaos_naive_unique_event_seeker"
DETAIL:  Key (event_id, seeker_id)=(6, 14) already exists.
DB rows for (event, seeker): [{'id': 9, 'status': 'CANCELLED', ...}]
```

Source: `chaos/artifacts/chaos_b_unique_together.log` via
`python chaos/chaos_b_unique_together.py`.

### Symptom B — Wrong PostgreSQL DDL for partial uniqueness

Attempting to express a conditional unique as a table constraint failed:

```sql
ALTER TABLE events_enrollment
ADD CONSTRAINT ... UNIQUE (event_id, seeker_id)
WHERE (status = 'ENROLLED');
```

Captured error (`chaos/artifacts/partial_unique_syntax_error.log`):

```text
psycopg2.errors.SyntaxError: syntax error at or near "WHERE"
LINE 5:             WHERE (status = 'ENROLLED')
                    ^
django.db.utils.ProgrammingError: syntax error at or near "WHERE"
```

This also broke an early restore path in Chaos B that used the same invalid DDL.
Automated test DBs that only accept Django-emitted migrations were fine; raw SQL
restores were not.

### Diagnosis

1. Unconditional `unique_together` / `UNIQUE(event, seeker)` treats a `CANCELLED`
   audit row as a conflicting key, so a new `ENROLLED` insert is impossible.
2. PostgreSQL does **not** allow `WHERE` on `ALTER TABLE ... ADD CONSTRAINT UNIQUE`.
   Partial uniqueness must be a **unique index**:

```sql
CREATE UNIQUE INDEX unique_active_enrollment_per_seeker_event
ON events_enrollment (event_id, seeker_id)
WHERE (status = 'ENROLLED');
```

Django’s `UniqueConstraint(..., condition=Q(status='ENROLLED'))` emits exactly
this index form. Also note: `ALTER TABLE ... DROP CONSTRAINT` does **not** drop
that index — Chaos B had to `DROP INDEX IF EXISTS` as well.

### Root Cause

Lifecycle design requires multiple historical rows per `(event, seeker)` while
enforcing “at most one **active** enrollment.” A full-table unique key cannot
encode that state machine. Manual DDL that mirrored the ORM constraint with
`ALTER TABLE ... WHERE` is invalid PostgreSQL.

### Fix

```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=["event", "seeker"],
            condition=Q(status="ENROLLED"),
            name="unique_active_enrollment_per_seeker_event",
        ),
    ]
```

Cancel keeps the row (`status=CANCELLED`). Re-enroll inserts a **new** `ENROLLED`
row so cancelled rows remain as audit history.

### Verification

```bash
python chaos/chaos_b_unique_together.py
# after restore:
# FIX VERIFIED — re-enrolled enrollment_id=...

python manage.py test events.tests.test_lifecycle -v 2
# test_enroll_cancel_reenroll_keeps_cancelled_audit_rows ... ok
# test_partial_unique_constraint_blocks_two_enrolled_rows ... ok
# test_api_enroll_cancel_reenroll ... ok
```

---

## How to re-run the live break-and-fix demos

```bash
# Postgres must be up; migrations applied
source .venv/bin/activate
python chaos/chaos_a_concurrency.py   # expect overbooking (5 > 1)
python chaos/chaos_b_unique_together.py  # expect IntegrityError, then fix verified
# or
bash chaos/run_all.sh
```

Inspect `chaos/artifacts/*.log` and paste fresh traces into this file when re-running.
