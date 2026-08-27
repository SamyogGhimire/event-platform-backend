"""
Enrollment lifecycle tests — Challenge B.

Validates cancel → re-enroll works under the partial unique constraint,
and that two concurrent active enrollments for the same seeker/event fail.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Profile, Role
from config.exceptions import APIError
from events.models import Enrollment, Event
from events.services import cancel_enrollment, enroll_seeker

User = get_user_model()


class EnrollmentLifecycleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.facilitator = User.objects.create_user(
            username="fac2@example.com",
            email="fac2@example.com",
            password="Passw0rd!",
        )
        Profile.objects.create(
            user=self.facilitator,
            role=Role.FACILITATOR,
            is_email_verified=True,
        )
        self.seeker = User.objects.create_user(
            username="seek@example.com",
            email="seek@example.com",
            password="Passw0rd!",
        )
        Profile.objects.create(
            user=self.seeker, role=Role.SEEKER, is_email_verified=True
        )
        now = timezone.now()
        self.event = Event.objects.create(
            title="Lifecycle Workshop",
            description="Re-enrollment lifecycle",
            language="English",
            location="Kathmandu",
            starts_at=now + timedelta(days=5),
            ends_at=now + timedelta(days=5, hours=2),
            capacity=5,
            created_by=self.facilitator,
        )

    def test_enroll_cancel_reenroll_keeps_cancelled_audit_rows(self):
        e1 = enroll_seeker(self.event.pk, self.seeker)
        self.assertEqual(e1.status, Enrollment.Status.ENROLLED)

        cancelled = cancel_enrollment(self.event.pk, self.seeker)
        self.assertEqual(cancelled.status, Enrollment.Status.CANCELLED)
        self.assertEqual(cancelled.pk, e1.pk)

        e2 = enroll_seeker(self.event.pk, self.seeker)
        self.assertEqual(e2.status, Enrollment.Status.ENROLLED)
        self.assertNotEqual(e2.pk, e1.pk)

        rows = Enrollment.objects.filter(event=self.event, seeker=self.seeker)
        self.assertEqual(rows.count(), 2)
        self.assertEqual(
            rows.filter(status=Enrollment.Status.CANCELLED).count(), 1
        )
        self.assertEqual(
            rows.filter(status=Enrollment.Status.ENROLLED).count(), 1
        )

    def test_cannot_double_enroll_while_active(self):
        enroll_seeker(self.event.pk, self.seeker)
        with self.assertRaises(APIError) as ctx:
            enroll_seeker(self.event.pk, self.seeker)
        self.assertEqual(ctx.exception.detail_code, "already_enrolled")

    def test_partial_unique_constraint_blocks_two_enrolled_rows(self):
        Enrollment.objects.create(
            event=self.event,
            seeker=self.seeker,
            status=Enrollment.Status.ENROLLED,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Enrollment.objects.create(
                    event=self.event,
                    seeker=self.seeker,
                    status=Enrollment.Status.ENROLLED,
                )

    def test_multiple_cancelled_rows_allowed(self):
        Enrollment.objects.create(
            event=self.event,
            seeker=self.seeker,
            status=Enrollment.Status.CANCELLED,
        )
        Enrollment.objects.create(
            event=self.event,
            seeker=self.seeker,
            status=Enrollment.Status.CANCELLED,
        )
        self.assertEqual(
            Enrollment.objects.filter(
                event=self.event,
                seeker=self.seeker,
                status=Enrollment.Status.CANCELLED,
            ).count(),
            2,
        )

    def test_api_enroll_cancel_reenroll(self):
        self.client.force_authenticate(user=self.seeker)
        r1 = self.client.post(f"/api/events/{self.event.pk}/enroll/")
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        r2 = self.client.post(f"/api/events/{self.event.pk}/cancel/")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["status"], "CANCELLED")

        r3 = self.client.post(f"/api/events/{self.event.pk}/enroll/")
        self.assertEqual(r3.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r3.data["status"], "ENROLLED")

    def test_capacity_full_standardized_error(self):
        self.event.capacity = 1
        self.event.save(update_fields=["capacity"])
        other = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="Passw0rd!",
        )
        Profile.objects.create(
            user=other, role=Role.SEEKER, is_email_verified=True
        )
        enroll_seeker(self.event.pk, other)

        self.client.force_authenticate(user=self.seeker)
        resp = self.client.post(f"/api/events/{self.event.pk}/enroll/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data, {
            "detail": "Event capacity full.",
            "code": "capacity_full",
        })

    def test_cannot_reduce_capacity_below_active_enrollments(self):
        # 8 active enrollments; shrinking capacity to 3 must fail.
        self.event.capacity = 10
        self.event.save(update_fields=["capacity"])
        enroll_seeker(self.event.pk, self.seeker)
        for i in range(7):
            u = User.objects.create_user(
                username=f"cap{i}@example.com",
                email=f"cap{i}@example.com",
                password="Passw0rd!",
            )
            Profile.objects.create(
                user=u, role=Role.SEEKER, is_email_verified=True
            )
            enroll_seeker(self.event.pk, u)

        self.client.force_authenticate(user=self.facilitator)
        resp = self.client.patch(
            f"/api/facilitator/events/{self.event.pk}/",
            {"capacity": 3},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            resp.data,
            {
                "detail": "Capacity cannot be lower than current active enrollments.",
                "code": "capacity_below_enrollment_count",
            },
        )

    def test_unlimited_capacity_enroll_and_available_seats_null(self):
        self.event.capacity = None
        self.event.save(update_fields=["capacity"])
        self.client.force_authenticate(user=self.seeker)
        enroll = self.client.post(f"/api/events/{self.event.pk}/enroll/")
        self.assertEqual(enroll.status_code, status.HTTP_201_CREATED)

        detail = self.client.get(f"/api/events/{self.event.pk}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertIsNone(detail.data["available_seats"])
        self.assertEqual(detail.data["enrollment_count"], 1)
        self.assertIsNone(detail.data["capacity"])

    def test_invalid_event_dates_ends_before_starts(self):
        self.client.force_authenticate(user=self.facilitator)
        now = timezone.now()
        resp = self.client.post(
            "/api/facilitator/events/",
            {
                "title": "Bad Dates",
                "description": "ends before starts",
                "language": "English",
                "location": "Remote",
                "starts_at": (now + timedelta(days=2)).isoformat(),
                "ends_at": (now + timedelta(days=1)).isoformat(),
                "capacity": 5,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", resp.data)
        self.assertIn("code", resp.data)

    def test_facilitator_list_includes_seat_counts(self):
        enroll_seeker(self.event.pk, self.seeker)
        self.client.force_authenticate(user=self.facilitator)
        resp = self.client.get("/api/facilitator/events/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        row = resp.data["results"][0]
        self.assertEqual(row["enrollment_count"], 1)
        self.assertEqual(row["available_seats"], 4)

    def test_event_search_filters(self):
        self.client.force_authenticate(user=self.seeker)
        resp = self.client.get(
            "/api/events/",
            {"q": "Lifecycle", "location": "Kathmandu", "language": "English"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data["count"], 1)
        self.assertIn("results", resp.data)
        self.assertIn("next", resp.data)
        self.assertIn("previous", resp.data)
