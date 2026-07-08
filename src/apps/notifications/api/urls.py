from django.urls import path

from apps.notifications.api.views import (
    NotificationCreateAPIView,
    NotificationDetailAPIView,
    NotificationListAPIView,
    NotificationMarkFailedAPIView,
    NotificationMarkSentAPIView,
)

app_name = "notifications"

urlpatterns = [
    path("", NotificationListAPIView.as_view(), name="list"),
    path("create/", NotificationCreateAPIView.as_view(), name="create"),
    path("<int:pk>/", NotificationDetailAPIView.as_view(), name="detail"),
    path("<int:notification_id>/send/", NotificationMarkSentAPIView.as_view(), name="send"),
    path("<int:notification_id>/fail/", NotificationMarkFailedAPIView.as_view(), name="fail"),
]
