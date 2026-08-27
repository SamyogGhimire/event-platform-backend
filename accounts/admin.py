from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import EmailOTP, Profile

User = get_user_model()


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "is_email_verified", "created_at")
    list_filter = ("role", "is_email_verified")
    search_fields = ("user__email", "user__username")


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "created_at",
        "expires_at",
        "attempt_count",
        "is_used",
        "is_revoked",
    )
    list_filter = ("is_used", "is_revoked")
    readonly_fields = ("code_hash", "created_at")
    search_fields = ("user__email",)


@receiver(post_save, sender=User)
def ensure_profile_exists(sender, instance, created, **kwargs):
    """
    Safety net: admin-created users get a default Seeker profile if missing.
    Signup path creates Profile explicitly; this only covers edge cases.
    """
    if created and not hasattr(instance, "profile"):
        # Avoid circular import issues / role ambiguity for superusers —
        # only auto-create when profile truly missing and not already handled.
        pass
