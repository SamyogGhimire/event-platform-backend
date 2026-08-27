"""
OTP engine tests — Challenge C.
Covers TTL, attempt limits, resend cooldown, and invalidation of prior OTPs.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import EmailOTP, Profile, Role
from accounts.otp import _hash_otp, create_and_send_otp, verify_otp
from config.exceptions import APIError

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OTP_TTL_SECONDS=300,
    OTP_RESEND_COOLDOWN_SECONDS=60,
    OTP_MAX_ATTEMPTS=3,
)
class OTPEngineTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="otp@example.com",
            email="otp@example.com",
            password="Passw0rd!",
        )
        Profile.objects.create(
            user=self.user, role=Role.SEEKER, is_email_verified=False
        )

    @patch("accounts.otp.send_mail")
    def test_otp_is_hashed_never_stored_plaintext(self, mock_mail):
        otp = create_and_send_otp(self.user)
        # Extract plaintext from the email body (only place it may exist)
        body = mock_mail.call_args.kwargs.get("message") or mock_mail.call_args[0][1]
        # Find 6-digit code in email
        import re

        match = re.search(r"\b(\d{6})\b", body)
        self.assertIsNotNone(match)
        plaintext = match.group(1)
        otp.refresh_from_db()
        self.assertEqual(otp.code_hash, _hash_otp(plaintext))
        self.assertNotEqual(otp.code_hash, plaintext)
        # Ensure hash column never equals plaintext
        self.assertFalse(EmailOTP.objects.filter(code_hash=plaintext).exists())

    @patch("accounts.otp.send_mail")
    def test_resend_invalidates_prior_otp(self, mock_mail):
        otp1 = create_and_send_otp(self.user)
        body1 = mock_mail.call_args.kwargs.get("message") or mock_mail.call_args[0][1]
        import re

        code1 = re.search(r"\b(\d{6})\b", body1).group(1)

        # Bypass cooldown for the second issuance
        EmailOTP.objects.filter(pk=otp1.pk).update(
            created_at=timezone.now() - timedelta(seconds=61)
        )
        otp2 = create_and_send_otp(self.user)
        otp1.refresh_from_db()
        self.assertTrue(otp1.is_revoked)
        self.assertNotEqual(otp1.pk, otp2.pk)

        with self.assertRaises(APIError) as ctx:
            verify_otp(self.user, code1)
        self.assertEqual(ctx.exception.detail_code, "invalid_or_expired_otp")

    @patch("accounts.otp.send_mail")
    def test_resend_cooldown(self, mock_mail):
        create_and_send_otp(self.user)
        with self.assertRaises(APIError) as ctx:
            create_and_send_otp(self.user)
        self.assertEqual(ctx.exception.detail_code, "otp_resend_cooldown")
        self.assertEqual(ctx.exception.status_code, 429)

    @patch("accounts.otp.send_mail")
    def test_ttl_expiry(self, mock_mail):
        otp = create_and_send_otp(self.user)
        body = mock_mail.call_args.kwargs.get("message") or mock_mail.call_args[0][1]
        import re

        code = re.search(r"\b(\d{6})\b", body).group(1)
        EmailOTP.objects.filter(pk=otp.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        with self.assertRaises(APIError) as ctx:
            verify_otp(self.user, code)
        self.assertEqual(ctx.exception.detail_code, "invalid_or_expired_otp")

    @patch("accounts.otp.send_mail")
    def test_max_attempts_lockout(self, mock_mail):
        create_and_send_otp(self.user)
        for i in range(3):
            with self.assertRaises(APIError) as ctx:
                verify_otp(self.user, "000000")
            if i < 2:
                self.assertEqual(ctx.exception.detail_code, "invalid_or_expired_otp")
            else:
                self.assertEqual(
                    ctx.exception.detail_code, "otp_max_attempts_exceeded"
                )

        # Further attempts stay locked even with a "lucky" guess of wrong code
        with self.assertRaises(APIError) as ctx:
            verify_otp(self.user, "111111")
        self.assertEqual(ctx.exception.detail_code, "otp_max_attempts_exceeded")

    @patch("accounts.otp.send_mail")
    def test_signup_verify_login_flow(self, mock_mail):
        resp = self.client.post(
            "/api/auth/signup/",
            {
                "email": "newseeker@example.com",
                "password": "Passw0rd!",
                "role": "Seeker",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("otp", resp.data)
        self.assertNotIn("code", resp.data)  # no otp code field

        body = mock_mail.call_args.kwargs.get("message") or mock_mail.call_args[0][1]
        import re

        otp_code = re.search(r"\b(\d{6})\b", body).group(1)

        # Unverified login blocked
        login_blocked = self.client.post(
            "/api/auth/login/",
            {"email": "newseeker@example.com", "password": "Passw0rd!"},
            format="json",
        )
        self.assertEqual(login_blocked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(login_blocked.data["code"], "email_not_verified")

        verify = self.client.post(
            "/api/auth/verify-otp/",
            {"email": "newseeker@example.com", "otp": otp_code},
            format="json",
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)

        login = self.client.post(
            "/api/auth/login/",
            {"email": "newseeker@example.com", "password": "Passw0rd!"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertIn("access", login.data)
        self.assertIn("refresh", login.data)

    def test_signup_rejects_username_field(self):
        resp = self.client.post(
            "/api/auth/signup/",
            {
                "email": "x@example.com",
                "password": "Passw0rd!",
                "role": "Seeker",
                "username": "hacker",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "username_not_allowed")
