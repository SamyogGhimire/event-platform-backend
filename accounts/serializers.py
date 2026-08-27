from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Profile, Role
from accounts.otp import create_and_send_otp, verify_otp
from config.exceptions import APIError

User = get_user_model()


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    role = serializers.ChoiceField(choices=Role.choices)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise APIError(
                detail="An account with this email already exists.",
                code="email_already_registered",
            )
        return email

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data["email"]
        password = validated_data["password"]
        role = validated_data["role"]

        # Username is required by default User model but must NOT appear in the
        # public API body — derive a unique username from the email.
        username = email
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_active=True,  # active for ORM, but login gated on email verification
        )
        Profile.objects.create(user=user, role=role, is_email_verified=False)
        create_and_send_otp(user, purpose="signup")
        return user


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate_email(self, value):
        return value.strip().lower()

    def save(self, **kwargs):
        email = self.validated_data["email"]
        otp = self.validated_data["otp"]
        try:
            user = User.objects.select_related("profile").get(email__iexact=email)
        except User.DoesNotExist as exc:
            raise APIError(
                detail="User not found.",
                code="user_not_found",
                status_code=404,
            ) from exc

        if user.profile.is_email_verified:
            raise APIError(
                detail="Email is already verified.",
                code="already_verified",
            )

        verify_otp(user, otp)
        user.profile.is_email_verified = True
        user.profile.save(update_fields=["is_email_verified", "updated_at"])
        return user


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()

    def save(self, **kwargs):
        email = self.validated_data["email"]
        try:
            user = User.objects.select_related("profile").get(email__iexact=email)
        except User.DoesNotExist as exc:
            raise APIError(
                detail="User not found.",
                code="user_not_found",
                status_code=404,
            ) from exc

        if user.profile.is_email_verified:
            raise APIError(
                detail="Email is already verified.",
                code="already_verified",
            )

        create_and_send_otp(user, purpose="resend")
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        password = attrs["password"]

        try:
            user = User.objects.select_related("profile").get(email__iexact=email)
        except User.DoesNotExist as exc:
            raise APIError(
                detail="Invalid email or password.",
                code="invalid_credentials",
                status_code=401,
            ) from exc

        if not user.check_password(password):
            raise APIError(
                detail="Invalid email or password.",
                code="invalid_credentials",
                status_code=401,
            )

        if not user.profile.is_email_verified:
            raise APIError(
                detail="Email is not verified. Please verify your OTP first.",
                code="email_not_verified",
                status_code=403,
            )

        if not user.is_active:
            raise APIError(
                detail="This account is disabled.",
                code="account_disabled",
                status_code=403,
            )

        attrs["user"] = user
        return attrs

    def create_tokens(self):
        user = self.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.pk,
                "email": user.email,
                "role": user.profile.role,
            },
        }


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Profile
        fields = ("email", "role", "is_email_verified", "created_at")
