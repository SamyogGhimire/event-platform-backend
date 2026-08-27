from django.urls import path

from events.views import (
    CancelEnrollmentView,
    EnrollView,
    EventDetailView,
    EventSearchView,
    FacilitatorEventDetailView,
    FacilitatorEventListCreateView,
    MyEnrollmentsView,
)

urlpatterns = [
    # Facilitator CRUD
    path(
        "facilitator/events/",
        FacilitatorEventListCreateView.as_view(),
        name="facilitator-event-list",
    ),
    path(
        "facilitator/events/<int:pk>/",
        FacilitatorEventDetailView.as_view(),
        name="facilitator-event-detail",
    ),
    # Public/seeker search + detail
    path("events/", EventSearchView.as_view(), name="event-search"),
    path("events/<int:pk>/", EventDetailView.as_view(), name="event-detail"),
    # Enrollments
    path(
        "events/<int:event_id>/enroll/",
        EnrollView.as_view(),
        name="event-enroll",
    ),
    path(
        "events/<int:event_id>/cancel/",
        CancelEnrollmentView.as_view(),
        name="event-cancel",
    ),
    path(
        "enrollments/me/",
        MyEnrollmentsView.as_view(),
        name="my-enrollments",
    ),
]
