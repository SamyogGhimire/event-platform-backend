"""
OTP engine — Challenge C.

Security invariants:
- OTP codes are hashed with SHA-256 before DB write.
- Plaintext OTPs are NEVER returned in API responses.
- Plaintext OTPs are NEVER written to application loggers.
- Issuing a new OTP immediately revokes all prior active OTPs for that user.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from accounts.models import EmailOTP
from config.exceptions import APIError

logger = logging.getLogger("accounts.otp")


def _hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _generate_otp_code() -> str:
    # Cryptographically strong 6-digit code (000000–999999)
    return f"{secrets.randbelow(10**settings.OTP_LENGTH):0{settings.OTP_LENGTH}d}"


def create_and_send_otp(user, *, purpose: str = "email_verification") -> EmailOTP:
    """
    Revoke any previously active OTPs, create a new hashed OTP, email it.
    Enforces 60-second resend cooldown.
    """
    now = timezone.now()

    latest = (
        EmailOTP.objects.filter(user=user)
        .order_by("-created_at")
        .first()
    )
    if latest is not None:
        elapsed = (now - latest.created_at).total_seconds()
        if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
            retry_after = int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed)
            raise APIError(
                detail=f"Please wait {retry_after} seconds before requesting another OTP.",
                code="otp_resend_cooldown",
                status_code=429,
            )

    code = _generate_otp_code()
    code_hash = _hash_otp(code)
    expires_at = now + timedelta(seconds=settings.OTP_TTL_SECONDS)

    with transaction.atomic():
        # Immediate invalidation of prior active OTPs (Challenge C)
        revoked_count = (
            EmailOTP.objects.select_for_update()
            .filter(user=user, is_used=False, is_revoked=False)
            .update(is_revoked=True)
        )
        otp = EmailOTP.objects.create(
            user=user,
            code_hash=code_hash,
            expires_at=expires_at,
        )

    # Log metadata only — never the plaintext code
    logger.info(
        "OTP issued user_id=%s purpose=%s otp_id=%s revoked_prior=%s expires_at=%s",
        user.pk,
        purpose,
        otp.pk,
        revoked_count,
        expires_at.isoformat(),
    )

    send_mail(
        subject="Your Events Platform verification code",
        message=(
            f"Your verification code is: {code}\n\n"
            f"It expires in {settings.OTP_TTL_SECONDS // 60} minutes.\n"
            "If you did not request this, ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return otp


def verify_otp(user, code: str) -> None:
    """
    Validate the submitted OTP against the latest active record.
    Raises APIError with stable error codes on failure.

    Important: increment attempt_count and commit BEFORE raising, otherwise
    the surrounding atomic() block would roll back the counter on APIError.
    """
    if not code or not code.isdigit() or len(code) != settings.OTP_LENGTH:
        raise APIError(
            detail="Invalid OTP format.",
            code="invalid_otp_format",
        )

    failure: APIError | None = None

    with transaction.atomic():
        otp = (
            EmailOTP.objects.select_for_update()
            .filter(user=user, is_used=False, is_revoked=False)
            .order_by("-created_at")
            .first()
        )

        if otp is None:
            failure = APIError(
                detail="No active OTP found. Please request a new one.",
                code="invalid_or_expired_otp",
            )
        elif otp.is_expired:
            otp.is_revoked = True
            otp.save(update_fields=["is_revoked"])
            failure = APIError(
                detail="OTP has expired. Please request a new one.",
                code="invalid_or_expired_otp",
            )
        elif otp.is_locked:
            failure = APIError(
                detail="Too many failed attempts. Please request a new OTP.",
                code="otp_max_attempts_exceeded",
            )
        elif otp.code_hash != _hash_otp(code):
            otp.attempt_count += 1
            otp.save(update_fields=["attempt_count"])
            logger.info(
                "OTP verify failed user_id=%s otp_id=%s attempts=%s",
                user.pk,
                otp.pk,
                otp.attempt_count,
            )
            remaining = settings.OTP_MAX_ATTEMPTS - otp.attempt_count
            if remaining <= 0:
                failure = APIError(
                    detail="Too many failed attempts. Please request a new OTP.",
                    code="otp_max_attempts_exceeded",
                )
            else:
                failure = APIError(
                    detail=f"Incorrect OTP. {remaining} attempt(s) remaining.",
                    code="invalid_or_expired_otp",
                )
        else:
            otp.is_used = True
            otp.save(update_fields=["is_used"])
            logger.info("OTP verified user_id=%s otp_id=%s", user.pk, otp.pk)
            return

    if failure is not None:
        raise failure
