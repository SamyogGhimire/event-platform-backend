from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import (
    LoginSerializer,
    ProfileSerializer,
    ResendOTPSerializer,
    SignupSerializer,
    VerifyOTPSerializer,
)


class SignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Reject username if a client tries to sneak it in
        if "username" in request.data:
            return Response(
                {
                    "detail": "Do not include username in the request body.",
                    "code": "username_not_allowed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "detail": "Signup successful. A verification OTP has been sent to your email.",
                "email": user.email,
                "role": user.profile.role,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Email verified successfully. You can now log in."},
            status=status.HTTP_200_OK,
        )


class ResendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "A new verification OTP has been sent to your email."},
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if "username" in request.data:
            return Response(
                {
                    "detail": "Use email, not username, to log in.",
                    "code": "username_not_allowed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.create_tokens(), status=status.HTTP_200_OK)


class MeView(APIView):
    def get(self, request):
        return Response(ProfileSerializer(request.user.profile).data)
