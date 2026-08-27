#!/usr/bin/env python
"""
Chaos Experiment B — Naive unique_together breaks re-enrollment

Applies a temporary UNIQUE(event_id, seeker_id) constraint (no status
condition), then runs Enroll → Cancel → Re-enroll to capture IntegrityError.

Usage:

    python chaos/chaos_b_unique_together.py

Artifacts written to chaos/artifacts/chaos_b_*.log
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import timedelta
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection, transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from accounts.models import Profile, Role  # noqa: E402
from events.models import Enrollment, Event  # noqa: E402

User = get_user_model()
ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = ARTIFACT_DIR / "chaos_b_unique_together.log"

NAIVE_CONSTRAINT = "chaos_naive_unique_event_seeker"
PARTIAL_CONSTRAINT = "unique_active_enrollment_per_seeker_event"


def log(msg: str) -> None:
    line = msg.rstrip()
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def drop_constraint(name: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f'ALTER TABLE events_enrollment DROP CONSTRAINT IF EXISTS "{name}"'
        )
        # Django UniqueConstraint(condition=...) is created as a UNIQUE INDEX,
        # not a table CONSTRAINT — drop both forms for a clean swap.
        cursor.execute(f'DROP INDEX IF EXISTS "{name}"')


def add_naive_unique() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            ALTER TABLE events_enrollment
            ADD CONSTRAINT {NAIVE_CONSTRAINT}
            UNIQUE (event_id, seeker_id)
            """
        )


def restore_partial_unique() -> None:
    """
    PostgreSQL does NOT support:
        ALTER TABLE ... ADD CONSTRAINT ... UNIQUE (...) WHERE ...
    Partial uniqueness requires a unique index:
        CREATE UNIQUE INDEX ... ON ... (...) WHERE ...
    Django's UniqueConstraint(condition=...) emits this index form.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {PARTIAL_CONSTRAINT}
            ON events_enrollment (event_id, seeker_id)
            WHERE (status = 'ENROLLED')
            """
        )


def main() -> int:
    LOG_PATH.write_text("", encoding="utf-8")
    log("=" * 72)
    log("CHAOS EXPERIMENT B — Naive unique_together blocks re-enrollment")
    log("=" * 72)

    # Ensure clean slate for this experiment's constraints + prior chaos rows
    drop_constraint(NAIVE_CONSTRAINT)
    drop_constraint(PARTIAL_CONSTRAINT)

    # Remove leftover chaos-B rows that would block a naive UNIQUE(event, seeker)
    Enrollment.objects.filter(seeker__email="chaos-b-seeker@example.com").delete()
    Event.objects.filter(title__startswith="CHAOS-B").delete()

    remaining = Enrollment.objects.filter(
        seeker__email="chaos-b-seeker@example.com"
    ).count()
    log(f"Pre-clean: chaos-b seeker enrollments remaining={remaining}")

    log("Installing NAIVE UNIQUE(event_id, seeker_id) — no status condition…")
    try:
        add_naive_unique()
    except Exception as exc:
        # Demonstrate the partial-index syntax footgun if someone uses wrong DDL
        log(f"Naive unique install failed unexpectedly: {exc!r}")
        log(traceback.format_exc())
        restore_partial_unique()
        return 1
    log(f"Installed constraint: {NAIVE_CONSTRAINT}")

    # Also capture the WRONG DDL syntax error for DEBUGGING.md evidence
    log("Demonstrating invalid PostgreSQL DDL for partial UNIQUE CONSTRAINT…")
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                ALTER TABLE events_enrollment
                ADD CONSTRAINT chaos_invalid_partial_unique
                UNIQUE (event_id, seeker_id)
                WHERE (status = 'ENROLLED')
                """
            )
    except Exception as exc:
        log(f"EXPECTED SYNTAX ERROR (partial unique via ALTER TABLE): {exc!r}")
        log(traceback.format_exc())
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE events_enrollment "
                "DROP CONSTRAINT IF EXISTS chaos_invalid_partial_unique"
            )

    fac, _ = User.objects.get_or_create(
        email="chaos-b-fac@example.com",
        defaults={"username": "chaos-b-fac@example.com"},
    )
    fac.set_password("Passw0rd!")
    fac.save()
    Profile.objects.update_or_create(
        user=fac,
        defaults={"role": Role.FACILITATOR, "is_email_verified": True},
    )

    email = "chaos-b-seeker@example.com"
    seeker, _ = User.objects.get_or_create(
        email=email, defaults={"username": email}
    )
    seeker.set_password("Passw0rd!")
    seeker.save()
    Profile.objects.update_or_create(
        user=seeker,
        defaults={"role": Role.SEEKER, "is_email_verified": True},
    )

    now = timezone.now()
    event = Event.objects.create(
        title="CHAOS-B Reenrollment Trap",
        description="unique_together demo",
        language="English",
        location="ChaosLab",
        starts_at=now + timedelta(days=2),
        ends_at=now + timedelta(days=2, hours=2),
        capacity=10,
        created_by=fac,
    )
    log(f"Created event id={event.pk}")

    # Step 1: enroll
    e1 = Enrollment.objects.create(
        event=event, seeker=seeker, status=Enrollment.Status.ENROLLED
    )
    log(f"STEP 1 ENROLLED enrollment_id={e1.pk} status={e1.status}")

    # Step 2: cancel (row retained for audit)
    e1.status = Enrollment.Status.CANCELLED
    e1.save(update_fields=["status", "updated_at"])
    log(f"STEP 2 CANCELLED enrollment_id={e1.pk} status={e1.status}")

    # Step 3: re-enroll by inserting a new ENROLLED row (audit-preserving design)
    log("STEP 3 RE-ENROLL — inserting new ENROLLED row…")
    integrity_error = None
    try:
        with transaction.atomic():
            e2 = Enrollment.objects.create(
                event=event, seeker=seeker, status=Enrollment.Status.ENROLLED
            )
            log(f"UNEXPECTED SUCCESS enrollment_id={e2.pk}")
    except Exception as exc:
        integrity_error = exc
        log(f"*** IntegrityError (or DB error) CAPTURED: {exc!r}")
        log(traceback.format_exc())

    # Capture DB state
    rows = list(
        Enrollment.objects.filter(event=event, seeker=seeker).values(
            "id", "status", "created_at", "updated_at"
        )
    )
    log(f"DB rows for (event, seeker): {rows}")

    # Restore production constraint
    log("Restoring production partial unique constraint…")
    drop_constraint(NAIVE_CONSTRAINT)
    try:
        restore_partial_unique()
        log(f"Restored: {PARTIAL_CONSTRAINT}")
    except Exception as exc:
        log(f"Restore warning: {exc!r}")
        log(traceback.format_exc())

    # Prove fix works
    log("Verifying re-enrollment works under partial unique constraint…")
    try:
        with transaction.atomic():
            e3 = Enrollment.objects.create(
                event=event, seeker=seeker, status=Enrollment.Status.ENROLLED
            )
        log(f"FIX VERIFIED — re-enrolled enrollment_id={e3.pk}")
        fix_ok = True
    except Exception as exc:
        log(f"Fix verification FAILED: {exc!r}")
        fix_ok = False

    log("-" * 72)
    if integrity_error is not None and fix_ok:
        log("*** CHAOS B COMPLETE — naive unique_together broken re-enrollment ***")
        log("Root cause: UNIQUE(event, seeker) treats CANCELLED rows as conflicts.")
        log(
            "Fix: UniqueConstraint(fields=[event,seeker], condition=Q(status='ENROLLED'))."
        )
        rc = 0
    else:
        log("Chaos B did not fully reproduce expected failure/fix cycle.")
        rc = 1

    log(f"Full log: {LOG_PATH}")
    log("=" * 72)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
