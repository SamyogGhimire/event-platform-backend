# Chaos Experiment Playbook — Break the System Yourself

Run these **before** trusting the production path. Capture terminal output into
`DEBUGGING.md`. Committed evidence from our live runs is under
[`docs/proof/`](../docs/proof/) (ZIP-safe). Local re-runs still write to
gitignored `chaos/artifacts/`.

## Prerequisites

```bash
cd events-platform
source .venv/bin/activate
# Postgres up, migrations applied
python manage.py migrate
```

---

## Experiment A — Concurrency overbooking

**Goal:** Watch capacity=1 accept multiple simultaneous enrollments when locking is absent.

```bash
python chaos/chaos_a_concurrency.py
```

**What to watch for**

- Five `[THREAD OK]` lines
- `FINAL active ENROLLED count = 5 (capacity was 1)`
- Banner: `OVERBOOKING CONFIRMED`

**Contrast:** `python manage.py test events.tests.test_concurrency` uses the
locked `enroll_seeker` service and must end with exactly `capacity` active rows.

---

## Experiment B — Naive unique key vs re-enrollment

**Goal:** See PostgreSQL reject a legitimate re-enroll when `UNIQUE(event, seeker)`
ignores status.

```bash
python chaos/chaos_b_unique_together.py
```

**What to watch for**

1. `STEP 1 ENROLLED` / `STEP 2 CANCELLED`
2. `IntegrityError` / `UniqueViolation` on STEP 3
3. Demo of invalid DDL: `syntax error at or near "WHERE"`
4. After restore: `FIX VERIFIED — re-enrolled`

**Contrast:** production `UniqueConstraint(condition=Q(status='ENROLLED'))` +
`test_lifecycle.py`.

---

## After chaos

Confirm the production index is present:

```bash
python - <<'PY'
import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute("""
      SELECT indexdef FROM pg_indexes
      WHERE indexname = 'unique_active_enrollment_per_seeker_event'
    """)
    print(c.fetchone())
PY
```

Then re-run the full suite:

```bash
python manage.py test accounts.tests events.tests -v 2
```

![06 — Test suite after chaos experiments](../docs/proof/06-test-suite.png)
