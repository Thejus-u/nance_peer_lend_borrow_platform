from django.urls import path

from apps.accounts.api.views import (
    ConnectGmailAPIView,
    CurrentUserAPIView,
    GmailAccountListAPIView,
    LoginAPIView,
    LogoutAPIView,
    RefreshGmailTokenAPIView,
    RefreshTokenAPIView,
    RegisterAPIView,
    SyncGmailEmailsAPIView,
)

app_name = "accounts"

urlpatterns = [
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/login/", LoginAPIView.as_view(), name="login"),
    path("auth/token/refresh/", RefreshTokenAPIView.as_view(), name="token_refresh"),
    path("auth/me/", CurrentUserAPIView.as_view(), name="current_user"),
    path("auth/logout/", LogoutAPIView.as_view(), name="logout"),
    path("auth/gmail/accounts/", GmailAccountListAPIView.as_view(), name="gmail_accounts"),
    path("auth/gmail/connect/", ConnectGmailAPIView.as_view(), name="gmail_connect"),
    path("auth/gmail/refresh/", RefreshGmailTokenAPIView.as_view(), name="gmail_refresh"),
    path("auth/gmail/sync/", SyncGmailEmailsAPIView.as_view(), name="gmail_sync"),
]