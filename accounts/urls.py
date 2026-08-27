from django.urls import path

from accounts.views import LoginView, MeView, ResendOTPView, SignupView, VerifyOTPView

urlpatterns = [
    path("signup/", SignupView.as_view(), name="auth-signup"),
    path("verify-otp/", VerifyOTPView.as_view(), name="auth-verify-otp"),
    path("resend-otp/", ResendOTPView.as_view(), name="auth-resend-otp"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("me/", MeView.as_view(), name="auth-me"),
]
