"""
Enrollment service — Challenge A (concurrency) + Challenge B (lifecycle).

Locking strategy:
  transaction.atomic() + Event.objects.select_for_update()
  serializes concurrent enrollments against the same event row so the
  active ENROLLED count can never exceed capacity.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Count, Q

from config.exceptions import APIError
from events.models import Enrollment, Event

logger = logging.getLogger("events.enrollment")


def enroll_seeker(event_id: int, seeker) -> Enrollment:
    """
    Enroll a seeker into an event with pessimistic locking.

    Guarantees: for capacity=N, active ENROLLED rows never exceed N even under
    simultaneous requests (verified by test_concurrency.py).
    """
    with transaction.atomic():
        # Pessimistic lock on the event row — concurrent enrollments for the
        # same event queue behind this lock.
        try:
            event = Event.objects.select_for_update().get(pk=event_id)
        except Event.DoesNotExist as exc:
            raise APIError(
                detail="Event not found.",
                code="event_not_found",
                status_code=404,
            ) from exc

        active = (
            Enrollment.objects.select_for_update()
            .filter(event=event, seeker=seeker, status=Enrollment.Status.ENROLLED)
            .first()
        )
        if active is not None:
            raise APIError(
                detail="You are already enrolled in this event.",
                code="already_enrolled",
            )

        if event.capacity is not None:
            enrolled_count = (
                Enrollment.objects.filter(
                    event=event, status=Enrollment.Status.ENROLLED
                ).count()
            )
            if enrolled_count >= event.capacity:
                logger.info(
                    "capacity_full event_id=%s capacity=%s enrolled=%s seeker_id=%s",
                    event.pk,
                    event.capacity,
                    enrolled_count,
                    seeker.pk,
                )
                raise APIError(
                    detail="Event capacity full.",
                    code="capacity_full",
                )

        # Always INSERT a new ENROLLED row. Prior CANCELLED rows remain as
        # audit history. The partial UniqueConstraint(condition=ENROLLED)
        # still guarantees at most one active enrollment per (event, seeker).
        prior_cancellations = Enrollment.objects.filter(
            event=event, seeker=seeker, status=Enrollment.Status.CANCELLED
        ).count()

        enrollment = Enrollment.objects.create(
            event=event,
            seeker=seeker,
            status=Enrollment.Status.ENROLLED,
        )
        logger.info(
            "enrolled event_id=%s seeker_id=%s enrollment_id=%s prior_cancellations=%s",
            event.pk,
            seeker.pk,
            enrollment.pk,
            prior_cancellations,
        )
        return enrollment


def cancel_enrollment(event_id: int, seeker) -> Enrollment:
    with transaction.atomic():
        try:
            enrollment = (
                Enrollment.objects.select_for_update()
                .select_related("event")
                .get(
                    event_id=event_id,
                    seeker=seeker,
                    status=Enrollment.Status.ENROLLED,
                )
            )
        except Enrollment.DoesNotExist as exc:
            raise APIError(
                detail="Active enrollment not found.",
                code="enrollment_not_found",
                status_code=404,
            ) from exc

        enrollment.status = Enrollment.Status.CANCELLED
        enrollment.save(update_fields=["status", "updated_at"])
        logger.info(
            "cancelled event_id=%s seeker_id=%s enrollment_id=%s",
            event_id,
            seeker.pk,
            enrollment.pk,
        )
        return enrollment


def annotate_seat_counts(queryset):
    """Annotate enrollment_count + available_seats for facilitator listings."""
    return queryset.annotate(
        _enrollment_count=Count(
            "enrollments",
            filter=Q(enrollments__status=Enrollment.Status.ENROLLED),
        )
    )
