"""
Enrollment concurrency stress tests — Challenge A.

Spawns parallel threads against a capacity-limited event and asserts the
active ENROLLED count never exceeds capacity.
"""
import threading
from datetime import timedelta
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import Profile, Role
from config.exceptions import APIError
from events.models import Enrollment, Event
from events.services import enroll_seeker

User = get_user_model()


def _using_postgres() -> bool:
    return "postgresql" in settings.DATABASES["default"]["ENGINE"]


@skipUnless(_using_postgres(), "Concurrency locking tests require PostgreSQL")
class EnrollmentConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.facilitator = User.objects.create_user(
            username="fac@example.com",
            email="fac@example.com",
            password="Passw0rd!",
        )
        Profile.objects.create(
            user=self.facilitator,
            role=Role.FACILITATOR,
            is_email_verified=True,
        )
        now = timezone.now()
        self.event = Event.objects.create(
            title="Capacity Race",
            description="Concurrency stress event",
            language="English",
            location="Remote",
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=1, hours=2),
            capacity=10,
            created_by=self.facilitator,
        )
        # Pre-fill 9 seats
        for i in range(9):
            u = User.objects.create_user(
                username=f"pre{i}@example.com",
                email=f"pre{i}@example.com",
                password="Passw0rd!",
            )
            Profile.objects.create(
                user=u, role=Role.SEEKER, is_email_verified=True
            )
            Enrollment.objects.create(
                event=self.event, seeker=u, status=Enrollment.Status.ENROLLED
            )

        self.racers = []
        for i in range(5):
            u = User.objects.create_user(
                username=f"racer{i}@example.com",
                email=f"racer{i}@example.com",
                password="Passw0rd!",
            )
            Profile.objects.create(
                user=u, role=Role.SEEKER, is_email_verified=True
            )
            self.racers.append(u)

    def test_parallel_enrollment_never_exceeds_capacity(self):
        results = {"ok": 0, "full": 0, "other": 0}
        lock = threading.Lock()
        barrier = threading.Barrier(len(self.racers))

        def worker(seeker):
            # Each thread needs its own DB connection
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                enroll_seeker(self.event.pk, seeker)
                with lock:
                    results["ok"] += 1
            except APIError as exc:
                with lock:
                    if exc.detail_code == "capacity_full":
                        results["full"] += 1
                    else:
                        results["other"] += 1
            except Exception:
                with lock:
                    results["other"] += 1
            finally:
                connection.close()

        threads = [
            threading.Thread(target=worker, args=(seeker,))
            for seeker in self.racers
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        active = Enrollment.objects.filter(
            event=self.event, status=Enrollment.Status.ENROLLED
        ).count()

        self.assertEqual(active, 10, f"Overbooking detected: {active} > 10")
        self.assertEqual(results["ok"], 1)
        self.assertEqual(results["full"], 4)
        self.assertEqual(results["other"], 0)

    def test_capacity_one_five_parallel_seekers(self):
        now = timezone.now()
        tiny = Event.objects.create(
            title="Tiny Room",
            description="capacity=1",
            language="English",
            location="Remote",
            starts_at=now + timedelta(days=2),
            ends_at=now + timedelta(days=2, hours=1),
            capacity=1,
            created_by=self.facilitator,
        )
        results = {"ok": 0, "full": 0}
        lock = threading.Lock()
        barrier = threading.Barrier(5)

        def worker(seeker):
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                enroll_seeker(tiny.pk, seeker)
                with lock:
                    results["ok"] += 1
            except APIError as exc:
                if exc.detail_code == "capacity_full":
                    with lock:
                        results["full"] += 1
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(s,)) for s in self.racers]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        active = Enrollment.objects.filter(
            event=tiny, status=Enrollment.Status.ENROLLED
        ).count()
        self.assertEqual(active, 1)
        self.assertEqual(results["ok"], 1)
        self.assertEqual(results["full"], 4)
