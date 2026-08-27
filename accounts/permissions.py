from rest_framework.permissions import BasePermission

from accounts.models import Role


class IsEmailVerified(BasePermission):
    message = "Email is not verified."
    code = "email_not_verified"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and hasattr(user, "profile")
            and user.profile.is_email_verified
        )


class IsFacilitator(BasePermission):
    message = "Facilitator role required."
    code = "facilitator_required"

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, "profile")
            and request.user.profile.role == Role.FACILITATOR
        )


class IsSeeker(BasePermission):
    message = "Seeker role required."
    code = "seeker_required"

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, "profile")
            and request.user.profile.role == Role.SEEKER
        )
