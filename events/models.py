from django.conf import settings
from django.db import models
from django.db.models import Q


class Event(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    language = models.CharField(max_length=64)
    location = models.CharField(max_length=255)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Null means unlimited capacity.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [
            models.Index(fields=["starts_at"]),
            models.Index(fields=["location"]),
            models.Index(fields=["language"]),
            models.Index(fields=["created_by", "starts_at"]),
            models.Index(fields=["location", "language", "starts_at"]),
        ]

    def __str__(self):
        return f"{self.title} @ {self.starts_at.isoformat()}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "ends_at must be after starts_at."})

    @property
    def enrollment_count(self) -> int:
        return self.enrollments.filter(status=Enrollment.Status.ENROLLED).count()

    @property
    def available_seats(self):
        if self.capacity is None:
            return None
        return max(self.capacity - self.enrollment_count, 0)


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ENROLLED = "ENROLLED", "Enrolled"
        CANCELLED = "CANCELLED", "Cancelled"

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    seeker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ENROLLED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event", "status"]),
            models.Index(fields=["seeker", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]
        constraints = [
            # Challenge B: at most ONE active enrollment per (event, seeker).
            # Cancelled rows remain as audit history and do NOT block re-enrollment.
            models.UniqueConstraint(
                fields=["event", "seeker"],
                condition=Q(status="ENROLLED"),
                name="unique_active_enrollment_per_seeker_event",
            ),
        ]

    def __str__(self):
        return f"Enrollment(event={self.event_id}, seeker={self.seeker_id}, {self.status})"
