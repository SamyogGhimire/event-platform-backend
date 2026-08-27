"""
Prove the API error contract: every representative failure status returns
{"detail": "...", "code": "..."}.
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


def assert_standardized_error(testcase, resp, expected_status):
    testcase.assertEqual(resp.status_code, expected_status)
    testcase.assertIsInstance(resp.data, dict)
    testcase.assertIn("detail", resp.data)
    testcase.assertIn("code", resp.data)
    testcase.assertIsInstance(resp.data["detail"], str)
    testcase.assertTrue(resp.data["detail"])
    testcase.assertIsInstance(resp.data["code"], str)
    testcase.assertTrue(resp.data["code"])
    testcase.assertEqual(set(resp.data.keys()), {"detail", "code"})


class StandardizedErrorContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        now = timezone.now()
        self.facilitator = User.objects.create_user(
            username="err_fac@example.com",
            email="err_fac@example.com",
            password="Passw0rd!",
        )
        Profile.objects.create(
            user=self.facilitator,
            role=Role.FACILITATOR,
            is_email_verified=True,
        )
        self.seeker = User.objects.create_user(
            username="err_seek@example.com",
            email="err_seek@example.com",
            password="Passw0rd!",
        )
        Profile.objects.create(
            user=self.seeker,
            role=Role.SEEKER,
            is_email_verified=True,
        )
        self.event = Event.objects.create(
            title="Error Contract Event",
            description="for status-code shape checks",
            language="English",
            location="Remote",
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=1, hours=2),
            capacity=5,
            created_by=self.facilitator,
        )

    def test_400_validation_error_shape(self):
        self.client.force_authenticate(user=self.facilitator)
        now = timezone.now()
        resp = self.client.post(
            "/api/facilitator/events/",
            {
                "title": "Bad",
                "description": "x",
                "language": "English",
                "location": "Remote",
                "starts_at": (now + timedelta(days=2)).isoformat(),
                "ends_at": (now + timedelta(days=1)).isoformat(),
                "capacity": 5,
            },
            format="json",
        )
        assert_standardized_error(self, resp, status.HTTP_400_BAD_REQUEST)

    def test_401_unauthenticated_error_shape(self):
        resp = self.client.get("/api/events/")
        assert_standardized_error(self, resp, status.HTTP_401_UNAUTHORIZED)

    def test_403_forbidden_error_shape(self):
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
        assert_standardized_error(self, resp, status.HTTP_403_FORBIDDEN)

    def test_404_not_found_error_shape(self):
        self.client.force_authenticate(user=self.seeker)
        resp = self.client.get("/api/events/999999/")
        assert_standardized_error(self, resp, status.HTTP_404_NOT_FOUND)
