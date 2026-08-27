"""
Authorization and permission error-code tests.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Profile, Role
from events.models import Event

User = get_user_model()


class AuthorizationErrorCodeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        now = timezone.now()

        self.facilitator = User.objects.create_user(
            username="fac_authz@example.com",
            email="fac_authz@example.com",
            password="Passw0rd!",
        )
        Profile.objects.create(
            user=self.facilitator,
            role=Role.FACILITATOR,
            is_email_verified=True,
        )

        self.seeker = User.objects.create_user(
            username="seek_authz@example.com",
            email="seek_authz@example.com",
            password="Passw0rd!",
        )
        Profile.objects.create(
            user=self.seeker,
            role=Role.SEEKER,
            is_email_verified=True,
        )

        self.unverified = User.objects.create_user(
            username="unv_authz@example.com",
            email="unv_authz@example.com",
            password="Passw0rd!",
        )
        Profile.objects.create(
            user=self.unverified,
            role=Role.SEEKER,
            is_email_verified=False,
        )

        self.event = Event.objects.create(
            title="Authz Event",
            description="Permission checks",
            language="English",
            location="Remote",
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=1, hours=2),
            capacity=5,
            created_by=self.facilitator,
        )

    def test_seeker_cannot_create_facilitator_event(self):
        self.client.force_authenticate(user=self.seeker)
        resp = self.client.post(
            "/api/facilitator/events/",
            {
                "title": "Nope",
                "description": "x",
                "language": "English",
                "location": "Remote",
                "starts_at": (timezone.now() + timedelta(days=2)).isoformat(),
                "ends_at": (timezone.now() + timedelta(days=2, hours=1)).isoformat(),
                "capacity": 3,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "facilitator_required")
        self.assertIn("detail", resp.data)

    def test_facilitator_cannot_enroll(self):
        self.client.force_authenticate(user=self.facilitator)
        resp = self.client.post(f"/api/events/{self.event.pk}/enroll/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "seeker_required")

    def test_unverified_user_gets_email_not_verified_code(self):
        self.client.force_authenticate(user=self.unverified)
        resp = self.client.get("/api/events/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "email_not_verified")

    def test_anonymous_gets_not_authenticated_code(self):
        resp = self.client.get("/api/events/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.data["code"], "not_authenticated")


class SearchTimezoneFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seeker = User.objects.create_user(
            username="tz@example.com",
            email="tz@example.com",
            password="Passw0rd!",
        )
        Profile.objects.create(
            user=self.seeker, role=Role.SEEKER, is_email_verified=True
        )
        self.facilitator = User.objects.create_user(
            username="tzfac@example.com",
            email="tzfac@example.com",
            password="Passw0rd!",
        )
        Profile.objects.create(
            user=self.facilitator,
            role=Role.FACILITATOR,
            is_email_verified=True,
        )
        now = timezone.now()
        self.early = Event.objects.create(
            title="Early Workshop",
            description="before window",
            language="English",
            location="Remote",
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=1, hours=1),
            capacity=10,
            created_by=self.facilitator,
        )
        self.late = Event.objects.create(
            title="Late Workshop",
            description="after window",
            language="English",
            location="Remote",
            starts_at=now + timedelta(days=10),
            ends_at=now + timedelta(days=10, hours=1),
            capacity=10,
            created_by=self.facilitator,
        )
        self.client.force_authenticate(user=self.seeker)

    def test_naive_starts_after_is_accepted_and_filters(self):
        """Naive ISO strings must not fail; treated as project timezone."""
        boundary = (timezone.now() + timedelta(days=5)).replace(tzinfo=None)
        naive = boundary.strftime("%Y-%m-%dT%H:%M:%S")
        resp = self.client.get("/api/events/", {"starts_after": naive})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in resp.data["results"]}
        self.assertNotIn(self.early.pk, ids)
        self.assertIn(self.late.pk, ids)

    def test_invalid_starts_after_standardized_error(self):
        resp = self.client.get("/api/events/", {"starts_after": "not-a-date"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_starts_after")
