from django.utils import timezone
from rest_framework import serializers

from events.models import Enrollment, Event


class EventSerializer(serializers.ModelSerializer):
    enrollment_count = serializers.SerializerMethodField()
    available_seats = serializers.SerializerMethodField()
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = Event
        fields = (
            "id",
            "title",
            "description",
            "language",
            "location",
            "starts_at",
            "ends_at",
            "capacity",
            "created_by",
            "created_by_email",
            "enrollment_count",
            "available_seats",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")

    def get_enrollment_count(self, obj):
        if hasattr(obj, "_enrollment_count"):
            return obj._enrollment_count
        return obj.enrollment_count

    def get_available_seats(self, obj):
        if obj.capacity is None:
            return None
        enrolled = self.get_enrollment_count(obj)
        return max(obj.capacity - enrolled, 0)

    def validate(self, attrs):
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError(
                {"ends_at": "ends_at must be after starts_at."}
            )
        capacity = attrs.get("capacity", getattr(self.instance, "capacity", None))
        if capacity is not None and capacity < 1:
            raise serializers.ValidationError(
                {"capacity": "capacity must be >= 1 when provided."}
            )
        return attrs


class EventWriteSerializer(EventSerializer):
    class Meta(EventSerializer.Meta):
        fields = (
            "id",
            "title",
            "description",
            "language",
            "location",
            "starts_at",
            "ends_at",
            "capacity",
            "created_at",
            "updated_at",
        )


class EnrollmentSerializer(serializers.ModelSerializer):
    event = EventSerializer(read_only=True)
    event_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Enrollment
        fields = (
            "id",
            "event",
            "event_id",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "status", "created_at", "updated_at", "event")


class EnrollmentListSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)
    event_starts_at = serializers.DateTimeField(source="event.starts_at", read_only=True)
    event_ends_at = serializers.DateTimeField(source="event.ends_at", read_only=True)
    event_location = serializers.CharField(source="event.location", read_only=True)
    is_upcoming = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = (
            "id",
            "event",
            "event_title",
            "event_starts_at",
            "event_ends_at",
            "event_location",
            "status",
            "is_upcoming",
            "created_at",
            "updated_at",
        )

    def get_is_upcoming(self, obj):
        return obj.event.starts_at >= timezone.now()
