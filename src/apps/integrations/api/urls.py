from django.urls import path

from apps.integrations.api.views import (
    GmailCallbackAPIView,
    GmailConnectAPIView,
    GmailMessageListAPIView,
    GmailStatusAPIView,
    GmailSyncAPIView,
)

app_name = "integrations"

urlpatterns = [
    path("gmail/connect/", GmailConnectAPIView.as_view(), name="gmail_connect"),
    path("gmail/callback/", GmailCallbackAPIView.as_view(), name="gmail_callback"),
    path("gmail/status/", GmailStatusAPIView.as_view(), name="gmail_status"),
    path("gmail/sync/", GmailSyncAPIView.as_view(), name="gmail_sync"),
    path("gmail/messages/", GmailMessageListAPIView.as_view(), name="gmail_messages"),
]
