"""
Seed demo users + sample events for evaluator walkthroughs.

Usage:
    python manage.py seed_demo
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile, Role
from events.models import Event

User = get_user_model()

DEMO_PASSWORD = "Passw0rd!"


class Command(BaseCommand):
    help = "Seed facilitator/seeker accounts and sample events."

    @transaction.atomic
    def handle(self, *args, **options):
        facilitator = self._ensure_user(
            email="facilitator@example.com",
            role=Role.FACILITATOR,
        )
        seekers = [
            self._ensure_user(email=f"seeker{i}@example.com", role=Role.SEEKER)
            for i in range(1, 6)
        ]

        now = timezone.now()
        samples = [
            {
                "title": "Intro to Django REST",
                "description": "Hands-on workshop covering DRF, JWT, and pagination.",
                "language": "English",
                "location": "Kathmandu",
                "starts_at": now + timedelta(days=3),
                "ends_at": now + timedelta(days=3, hours=2),
                "capacity": 10,
            },
            {
                "title": "PostgreSQL Concurrency Deep Dive",
                "description": "Locks, isolation levels, and select_for_update patterns.",
                "language": "English",
                "location": "Remote",
                "starts_at": now + timedelta(days=7),
                "ends_at": now + timedelta(days=7, hours=3),
                "capacity": 1,
            },
            {
                "title": "Nepali Language Meetup",
                "description": "Community meetup for Nepali speakers.",
                "language": "Nepali",
                "location": "Pokhara",
                "starts_at": now + timedelta(days=14),
                "ends_at": now + timedelta(days=14, hours=2),
                "capacity": None,
            },
        ]

        created_events = 0
        for data in samples:
            _, was_created = Event.objects.get_or_create(
                title=data["title"],
                created_by=facilitator,
                defaults=data,
            )
            if was_created:
                created_events += 1

        self.stdout.write(self.style.SUCCESS("Seed complete."))
        self.stdout.write(f"  Facilitator: facilitator@example.com / {DEMO_PASSWORD}")
        self.stdout.write(
            f"  Seekers: seeker1@example.com … seeker5@example.com / {DEMO_PASSWORD}"
        )
        self.stdout.write(f"  Events created this run: {created_events}")
        self.stdout.write("  All seeded users are email-verified (ready to login).")

    def _ensure_user(self, *, email: str, role: str):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"username": email},
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        Profile.objects.update_or_create(
            user=user,
            defaults={"role": role, "is_email_verified": True},
        )
        return user
