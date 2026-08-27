from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsEmailVerified, IsFacilitator, IsSeeker
from config.exceptions import APIError
from events.models import Enrollment, Event
from events.serializers import (
    EnrollmentListSerializer,
    EnrollmentSerializer,
    EventSerializer,
    EventWriteSerializer,
)
from events.services import annotate_seat_counts, cancel_enrollment, enroll_seeker


class IsEventOwner(permissions.BasePermission):
    message = "You may only modify events you created."
    code = "not_event_owner"

    def has_object_permission(self, request, view, obj):
        return obj.created_by_id == request.user.id


class FacilitatorEventListCreateView(generics.ListCreateAPIView):
    """Facilitator: list own events (with seat counts) + create."""

    permission_classes = [permissions.IsAuthenticated, IsEmailVerified, IsFacilitator]
    serializer_class = EventSerializer

    def get_queryset(self):
        qs = Event.objects.filter(created_by=self.request.user)
        return annotate_seat_counts(qs).order_by("starts_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return EventWriteSerializer
        return EventSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class FacilitatorEventDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [
        permissions.IsAuthenticated,
        IsEmailVerified,
        IsFacilitator,
        IsEventOwner,
    ]
    serializer_class = EventWriteSerializer
    lookup_field = "pk"

    def get_queryset(self):
        return annotate_seat_counts(
            Event.objects.filter(created_by=self.request.user)
        )

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return EventWriteSerializer
        return EventSerializer


class EventSearchView(generics.ListAPIView):
    """
    Seeker (and authenticated users): search/filter events.
    Query params: q, location, language, starts_after, starts_before.
    Default order: starts_at ASC (upcoming first).
    """

    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    serializer_class = EventSerializer

    def get_queryset(self):
        qs = annotate_seat_counts(Event.objects.all())
        params = self.request.query_params

        q = params.get("q")
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

        location = params.get("location")
        if location:
            qs = qs.filter(location__icontains=location)

        language = params.get("language")
        if language:
            qs = qs.filter(language__iexact=language)

        starts_after = params.get("starts_after")
        if starts_after:
            dt = parse_datetime(starts_after)
            if dt is None:
                raise APIError(
                    detail="Invalid starts_after datetime. Use ISO-8601.",
                    code="invalid_starts_after",
                )
            qs = qs.filter(starts_at__gte=dt)

        starts_before = params.get("starts_before")
        if starts_before:
            dt = parse_datetime(starts_before)
            if dt is None:
                raise APIError(
                    detail="Invalid starts_before datetime. Use ISO-8601.",
                    code="invalid_starts_before",
                )
            qs = qs.filter(starts_at__lte=dt)

        return qs.order_by("starts_at")


class EventDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    serializer_class = EventSerializer
    queryset = Event.objects.all()

    def get_queryset(self):
        return annotate_seat_counts(Event.objects.all())


class EnrollView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified, IsSeeker]

    def post(self, request, event_id):
        enrollment = enroll_seeker(event_id, request.user)
        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED,
        )


class CancelEnrollmentView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified, IsSeeker]

    def post(self, request, event_id):
        enrollment = cancel_enrollment(event_id, request.user)
        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_200_OK,
        )


class MyEnrollmentsView(generics.ListAPIView):
    """
    List seeker enrollments.
    ?scope=upcoming|past|all (default: all)
    ?status=ENROLLED|CANCELLED (optional)
    """

    permission_classes = [permissions.IsAuthenticated, IsEmailVerified, IsSeeker]
    serializer_class = EnrollmentListSerializer

    def get_queryset(self):
        qs = Enrollment.objects.filter(seeker=self.request.user).select_related("event")
        scope = self.request.query_params.get("scope", "all")
        now = timezone.now()
        if scope == "upcoming":
            qs = qs.filter(
                status=Enrollment.Status.ENROLLED,
                event__starts_at__gte=now,
            ).order_by("event__starts_at")
        elif scope == "past":
            qs = qs.filter(event__starts_at__lt=now).order_by("-event__starts_at")
        else:
            qs = qs.order_by("-created_at")

        status_filter = self.request.query_params.get("status")
        if status_filter in Enrollment.Status.values:
            qs = qs.filter(status=status_filter)
        return qs
