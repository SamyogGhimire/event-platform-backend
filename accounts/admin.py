from django.contrib import admin

from accounts.models import EmailOTP, Profile


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
