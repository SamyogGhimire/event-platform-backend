from django.conf import settings
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    SEEKER = "Seeker", "Seeker"
    FACILITATOR = "Facilitator", "Facilitator"


class Profile(models.Model):
    """
    1-to-1 extension of the default Django User.
    Roles live here — User model is never swapped or subclassed.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    is_email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["is_email_verified"]),
        ]

    def __str__(self):
        return f"{self.user.email} ({self.role})"

    @property
    def is_seeker(self):
        return self.role == Role.SEEKER

    @property
    def is_facilitator(self):
        return self.role == Role.FACILITATOR


class EmailOTP(models.Model):
    """
    Hashed email OTP. Plaintext codes are NEVER persisted or logged.
    Only one active (unused, unexpired, not revoked) OTP should exist per user
    at a time — requesting a new OTP revokes prior actives.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_otps",
    )
    code_hash = models.CharField(max_length=64)  # SHA-256 hex digest
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempt_count = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    is_revoked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["is_used", "is_revoked"]),
        ]

    def __str__(self):
        return f"OTP(user={self.user_id}, expires={self.expires_at}, revoked={self.is_revoked})"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_locked(self):
        from django.conf import settings as dj_settings

        return self.attempt_count >= dj_settings.OTP_MAX_ATTEMPTS

    @property
    def is_active(self):
        return (
            not self.is_used
            and not self.is_revoked
            and not self.is_expired
            and not self.is_locked
        )
