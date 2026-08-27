from django.contrib import admin

from events.models import Enrollment, Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "language",
        "location",
        "starts_at",
        "ends_at",
        "capacity",
        "created_by",
    )
    list_filter = ("language", "location")
    search_fields = ("title", "description", "location")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "seeker", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("event__title", "seeker__email")
