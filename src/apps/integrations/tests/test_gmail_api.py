from __future__ import annotations

import base64
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.integrations.models import DiscoveredEmail, GmailAccount
from apps.payments.models import BankTransaction, DiscoveredAccount


@override_settings(
    GMAIL_CLIENT_ID="gmail-client",
    GMAIL_CLIENT_SECRET="gmail-secret",
)
class GmailIntegrationAPITestCase(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            mobile_number="+14156660011",
            name="Integration User",
            password="StrongPass123!",
        )
        login_response = self.client.post(
            reverse("accounts:login"),
            {"mobile_number": self.user.mobile_number, "password": "StrongPass123!"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")

    def test_connect_returns_oauth_url(self) -> None:
        response = self.client.get(
            reverse("integrations:gmail_connect"),
            {
                "redirect_uri": "https://example.com/api/v1/integrations/gmail/callback/",
                "frontend_redirect": "https://example.com/app/discovered-accounts/",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("oauth_url", response.data)
        self.assertIn("accounts.google.com", response.data["oauth_url"])

    @patch("apps.integrations.services.gmail_oauth.GmailOAuthService._fetch_gmail_profile")
    @patch("apps.integrations.services.gmail_oauth.GmailOAuthService._exchange_auth_code")
    def test_callback_stores_tokens_and_status_hides_tokens(self, mock_exchange, mock_profile) -> None:
        mock_exchange.return_value = type(
            "Token",
            (),
            {
                "access_token": "token-1",
                "refresh_token": "refresh-1",
                "expires_in": 3600,
                "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly",
            },
        )()
        mock_profile.return_value = type("Profile", (), {"email": "alice@gmail.com", "sub": "sub-123"})()

        connect = self.client.get(
            reverse("integrations:gmail_connect"),
            {"redirect_uri": "https://example.com/api/v1/integrations/gmail/callback/"},
        )
        oauth_url = connect.data["oauth_url"]
        state = parse_qs(urlparse(oauth_url).query)["state"][0]

        callback = self.client.get(reverse("integrations:gmail_callback"), {"code": "code-123", "state": state})
        self.assertEqual(callback.status_code, status.HTTP_200_OK)

        account = GmailAccount.objects.get(user=self.user)
        self.assertEqual(account.email, "alice@gmail.com")
        self.assertNotEqual(account.access_token, "token-1")
        self.assertNotEqual(account.refresh_token, "refresh-1")
        self.assertEqual(account.get_access_token(), "token-1")
        self.assertEqual(account.get_refresh_token(), "refresh-1")

        status_response = self.client.get(reverse("integrations:gmail_status"))
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertEqual(status_response.data["connected"], True)
        self.assertEqual(status_response.data["email"], "alice@gmail.com")
        self.assertNotIn("refresh_token", status_response.data)
        self.assertNotIn("access_token", status_response.data)

    @patch("apps.integrations.services.gmail_oauth.GmailOAuthService._refresh_access_token")
    @patch("apps.integrations.services.gmail_api.GmailAPIService.fetch_message")
    @patch("apps.integrations.services.gmail_api.GmailAPIService.list_messages")
    def test_sync_refreshes_expired_token_and_populates_discovered_accounts(
        self,
        mock_list_messages,
        mock_fetch_message,
        mock_refresh,
    ) -> None:
        account = GmailAccount(user=self.user, email="sync@gmail.com", google_user_id="google-1")
        account.set_access_token("access-old")
        account.set_refresh_token("refresh-old")
        account.expires_at = timezone.now() - timedelta(minutes=1)
        account.save()

        mock_refresh.return_value = type(
            "Token",
            (),
            {
                "access_token": "access-new",
                "refresh_token": "refresh-new",
                "expires_in": 3600,
                "scope": "scope-1",
            },
        )()
        mock_list_messages.return_value = [{"id": "msg-1"}]
        body = base64.urlsafe_b64encode(
            b"Your account ending 1234 is debited by INR 450.00 via UPI to chai@oksbi. Ref UTR1234567."
        ).decode("utf-8")
        mock_fetch_message.return_value = {
            "id": "msg-1",
            "threadId": "thread-1",
            "snippet": "Debit notification",
            "payload": {
                "mimeType": "multipart/alternative",
                "parts": [{"mimeType": "text/plain", "body": {"data": body}}],
                "headers": [
                    {"name": "Subject", "value": "UPI Debit Alert"},
                    {"name": "From", "value": "alerts@alerts.hdfcbank.com"},
                    {"name": "Date", "value": "Mon, 01 Jul 2026 10:30:00 +0000"},
                ],
            },
        }

        response = self.client.post(
            reverse("integrations:gmail_sync"),
            {"gmail_account_id": account.id, "max_results": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["synced_count"], 1)
        self.assertEqual(response.data["parsed_count"], 1)
        self.assertEqual(response.data["discovered_account_count"], 1)
        self.assertEqual(response.data["fetched_email_count"], 1)
        self.assertEqual(DiscoveredEmail.objects.filter(gmail_account=account).count(), 1)
        self.assertEqual(BankTransaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(DiscoveredAccount.objects.filter(user=self.user).count(), 1)

        account.refresh_from_db()
        self.assertEqual(account.get_access_token(), "access-new")
        self.assertEqual(account.get_refresh_token(), "refresh-new")

    def test_messages_endpoint_returns_synced_messages(self) -> None:
        account = GmailAccount.objects.create(
            user=self.user,
            email="messages@gmail.com",
            google_user_id="google-2",
        )
        DiscoveredEmail.objects.create(
            gmail_account=account,
            gmail_message_id="msg-1",
            subject="Subject",
            sender="alerts@alerts.hdfcbank.com",
            processed=True,
            raw_payload={"id": "msg-1"},
        )

        response = self.client.get(reverse("integrations:gmail_messages"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["gmail_message_id"], "msg-1")