#!/usr/bin/env python
"""
Chaos Experiment A — Concurrency Overbooking

Deliberately removes select_for_update() and fires parallel enrollments
against capacity=1 so you can observe a real race / overbooking.

Usage (from project root, venv active, Postgres up, migrations applied):

    python chaos/chaos_a_concurrency.py

Artifacts written to chaos/artifacts/chaos_a_*.log
"""
from __future__ import annotations

import os
import sys
import threading
import traceback
from datetime import timedelta
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection, connections, transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from accounts.models import Profile, Role  # noqa: E402
from events.models import Enrollment, Event  # noqa: E402

User = get_user_model()
ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = ARTIFACT_DIR / "chaos_a_overbooking.log"


def log(msg: str) -> None:
    line = msg.rstrip()
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def broken_enroll_no_lock(event_id: int, seeker) -> Enrollment:
    """
    BROKEN enrollment path: no select_for_update().
    Reproduces the classic check-then-act race under concurrency.
    """
    with transaction.atomic():
        event = Event.objects.get(pk=event_id)  # <-- NO select_for_update()
        if Enrollment.objects.filter(
            event=event, seeker=seeker, status=Enrollment.Status.ENROLLED
        ).exists():
            raise RuntimeError("already_enrolled")

        enrolled_count = Enrollment.objects.filter(
            event=event, status=Enrollment.Status.ENROLLED
        ).count()

        # Artificial yield window enlarges the race for demonstration
        import time

        time.sleep(0.05)

        if event.capacity is not None and enrolled_count >= event.capacity:
            raise RuntimeError("capacity_full")

        return Enrollment.objects.create(
            event=event,
            seeker=seeker,
            status=Enrollment.Status.ENROLLED,
        )


def main() -> int:
    LOG_PATH.write_text("", encoding="utf-8")
    log("=" * 72)
    log("CHAOS EXPERIMENT A — Concurrency Overbooking (NO select_for_update)")
    log("=" * 72)

    fac, _ = User.objects.get_or_create(
        email="chaos-fac@example.com",
        defaults={"username": "chaos-fac@example.com"},
    )
    fac.set_password("Passw0rd!")
    fac.save()
    Profile.objects.update_or_create(
        user=fac,
        defaults={"role": Role.FACILITATOR, "is_email_verified": True},
    )

    now = timezone.now()
    event = Event.objects.create(
        title="CHAOS-A Tiny Room",
        description="capacity=1 race demo",
        language="English",
        location="ChaosLab",
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=1, hours=1),
        capacity=1,
        created_by=fac,
    )
    log(f"Created event id={event.pk} capacity=1")

    seekers = []
    for i in range(5):
        email = f"chaos-a-seeker{i}@example.com"
        u, _ = User.objects.get_or_create(
            email=email, defaults={"username": email}
        )
        u.set_password("Passw0rd!")
        u.save()
        Profile.objects.update_or_create(
            user=u,
            defaults={"role": Role.SEEKER, "is_email_verified": True},
        )
        seekers.append(u)

    results = {"ok": 0, "rejected": 0, "errors": []}
    lock = threading.Lock()
    barrier = threading.Barrier(len(seekers))

    def worker(seeker):
        connections.close_all()
        try:
            barrier.wait(timeout=15)
            enrollment = broken_enroll_no_lock(event.pk, seeker)
            with lock:
                results["ok"] += 1
                log(
                    f"[THREAD OK] seeker_id={seeker.pk} enrollment_id={enrollment.pk}"
                )
        except Exception as exc:
            with lock:
                results["rejected"] += 1
                results["errors"].append(repr(exc))
                log(f"[THREAD FAIL] seeker_id={seeker.pk} error={exc!r}")
                log(traceback.format_exc())
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(s,)) for s in seekers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    active = Enrollment.objects.filter(
        event=event, status=Enrollment.Status.ENROLLED
    ).count()
    log("-" * 72)
    log(f"FINAL active ENROLLED count = {active} (capacity was 1)")
    log(f"Thread successes = {results['ok']}, failures = {results['rejected']}")
    if active > 1:
        log("*** OVERBOOKING CONFIRMED — race condition reproduced ***")
        log("Root cause: check-then-act without row lock allowed concurrent inserts.")
        log("Fix: Event.objects.select_for_update() inside transaction.atomic().")
        rc = 0  # experiment succeeded in demonstrating the bug
    else:
        log(
            "Overbooking did not reproduce this run (scheduler timing). "
            "Re-run; the sleep(0.05) window usually triggers it."
        )
        rc = 1

    log(f"Full log: {LOG_PATH}")
    log("=" * 72)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
