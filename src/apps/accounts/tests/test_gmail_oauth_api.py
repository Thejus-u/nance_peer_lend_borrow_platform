from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch
import base64

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import GmailAccount, GmailSyncedEmail, User
from apps.payments.models import BankTransaction, DiscoveredAccount, DiscoveredAccountStatus


class GmailOAuthAPITestCase(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            mobile_number="+14156660001",
            name="Gmail User",
            password="StrongPass123!",
        )

        login_response = self.client.post(
            reverse("accounts:login"),
            {"mobile_number": self.user.mobile_number, "password": "StrongPass123!"},
            format="json",
        )
        self.access_token = login_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    @patch("apps.accounts.services.gmail_oauth_service.GmailOAuthService._fetch_gmail_profile")
    @patch("apps.accounts.services.gmail_oauth_service.GmailOAuthService._exchange_auth_code")
    def test_connect_gmail_creates_gmail_account(self, mock_exchange, mock_profile) -> None:
        mock_exchange.return_value = type("Token", (), {
            "access_token": "token-1",
            "refresh_token": "refresh-1",
            "expires_in": 3600,
            "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly",
        })()
        mock_profile.return_value = type("Profile", (), {"email": "alice@gmail.com", "sub": "sub-123"})()

        response = self.client.post(
            reverse("accounts:gmail_connect"),
            {
                "authorization_code": "code-123",
                "redirect_uri": "https://example.com/oauth/callback",
                "set_primary": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            GmailAccount.objects.filter(user=self.user, gmail_address="alice@gmail.com").exists()
        )

    @patch("apps.accounts.services.gmail_oauth_service.GmailOAuthService._refresh_access_token")
    def test_refresh_gmail_token_updates_access_token(self, mock_refresh) -> None:
        account = GmailAccount.objects.create(
            user=self.user,
            gmail_address="refresh@gmail.com",
            refresh_token="refresh-old",
            access_token="access-old",
            token_expires_at=timezone.now() - timedelta(minutes=1),
            token_scopes="scope-1",
        )

        mock_refresh.return_value = type("Token", (), {
            "access_token": "access-new",
            "refresh_token": "refresh-new",
            "expires_in": 3600,
            "scope": "scope-2",
        })()

        response = self.client.post(
            reverse("accounts:gmail_refresh"),
            {"gmail_account_id": account.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        account.refresh_from_db()
        self.assertEqual(account.access_token, "access-new")
        self.assertEqual(account.refresh_token, "refresh-new")

    @patch("apps.accounts.services.gmail_oauth_service.GmailOAuthService._list_messages")
    @patch("apps.accounts.services.gmail_oauth_service.GmailOAuthService._get_message")
    def test_sync_gmail_emails_persists_messages(self, mock_get_message, mock_list_messages) -> None:
        account = GmailAccount.objects.create(
            user=self.user,
            gmail_address="sync@gmail.com",
            refresh_token="refresh-sync",
            access_token="access-sync",
            token_expires_at=timezone.now() + timedelta(hours=1),
        )

        mock_list_messages.return_value = [{"id": "msg-1"}, {"id": "msg-2"}]
        body_one = base64.urlsafe_b64encode(
            b"Your account ending 1234 is debited by INR 450.00 via UPI to chai@oksbi. Ref UTR1234567."
        ).decode("utf-8")
        body_two = base64.urlsafe_b64encode(
            b"INR 899.50 credited to A/C XX8911 from rent@okaxis. Ref UTR1234568."
        ).decode("utf-8")

        mock_get_message.side_effect = [
            {
                "id": "msg-1",
                "threadId": "thread-1",
                "snippet": "Debit notification",
                "payload": {
                    "mimeType": "multipart/alternative",
                    "parts": [{"mimeType": "text/plain", "body": {"data": body_one}}],
                    "headers": [
                        {"name": "Subject", "value": "UPI Debit Alert"},
                        {"name": "From", "value": "alerts@alerts.hdfcbank.com"},
                        {"name": "Date", "value": "Mon, 01 Jul 2026 10:30:00 +0000"},
                    ]
                },
            },
            {
                "id": "msg-2",
                "threadId": "thread-2",
                "snippet": "Credit notification",
                "payload": {
                    "mimeType": "multipart/alternative",
                    "parts": [{"mimeType": "text/plain", "body": {"data": body_two}}],
                    "headers": [
                        {"name": "Subject", "value": "UPI Credit Alert"},
                        {"name": "From", "value": "notify@icicibank.com"},
                        {"name": "Date", "value": "Tue, 02 Jul 2026 11:30:00 +0000"},
                    ]
                },
            },
        ]

        response = self.client.post(
            reverse("accounts:gmail_sync"),
            {"gmail_account_id": account.id, "max_results": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["synced_count"], 2)
        self.assertEqual(response.data["ingested_transaction_count"], 2)
        self.assertEqual(response.data["discovered_account_count"], 2)
        self.assertEqual(GmailSyncedEmail.objects.filter(gmail_account=account).count(), 2)
        self.assertEqual(BankTransaction.objects.filter(user=self.user).count(), 2)
        self.assertEqual(DiscoveredAccount.objects.filter(user=self.user).count(), 2)

    @patch("apps.accounts.services.gmail_oauth_service.GmailOAuthService._list_messages")
    @patch("apps.accounts.services.gmail_oauth_service.GmailOAuthService._get_message")
    def test_sync_gmail_emails_prevents_duplicate_email_ingestion(self, mock_get_message, mock_list_messages) -> None:
        account = GmailAccount.objects.create(
            user=self.user,
            gmail_address="dedupe@gmail.com",
            refresh_token="refresh-sync",
            access_token="access-sync",
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        body_one = base64.urlsafe_b64encode(
            b"Your account ending 1234 is debited by INR 450.00 via UPI to chai@oksbi. Ref UTR1234567."
        ).decode("utf-8")

        mock_list_messages.return_value = [{"id": "msg-1"}]
        mock_get_message.return_value = {
            "id": "msg-1",
            "threadId": "thread-1",
            "snippet": "Debit notification",
            "payload": {
                "mimeType": "multipart/alternative",
                "parts": [{"mimeType": "text/plain", "body": {"data": body_one}}],
                "headers": [
                    {"name": "Subject", "value": "UPI Debit Alert"},
                    {"name": "From", "value": "alerts@alerts.hdfcbank.com"},
                    {"name": "Date", "value": "Mon, 01 Jul 2026 10:30:00 +0000"},
                ],
            },
        }

        first = self.client.post(
            reverse("accounts:gmail_sync"),
            {"gmail_account_id": account.id, "max_results": 10},
            format="json",
        )
        second = self.client.post(
            reverse("accounts:gmail_sync"),
            {"gmail_account_id": account.id, "max_results": 10},
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(BankTransaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(DiscoveredAccount.objects.filter(user=self.user).count(), 1)

    @patch("apps.accounts.services.gmail_oauth_service.GmailOAuthService._list_messages")
    @patch("apps.accounts.services.gmail_oauth_service.GmailOAuthService._get_message")
    def test_sync_gmail_emails_ignores_non_whitelisted_sender_and_promotional_mail(
        self,
        mock_get_message,
        mock_list_messages,
    ) -> None:
        account = GmailAccount.objects.create(
            user=self.user,
            gmail_address="ignore@gmail.com",
            refresh_token="refresh-sync",
            access_token="access-sync",
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        promo_body = base64.urlsafe_b64encode(
            b"Limited period promotional offer. Get cashback. Unsubscribe anytime."
        ).decode("utf-8")

        mock_list_messages.return_value = [{"id": "msg-1"}, {"id": "msg-2"}]
        mock_get_message.side_effect = [
            {
                "id": "msg-1",
                "threadId": "thread-1",
                "snippet": "random email",
                "payload": {
                    "parts": [{"mimeType": "text/plain", "body": {"data": promo_body}}],
                    "headers": [
                        {"name": "Subject", "value": "Promo offer"},
                        {"name": "From", "value": "deals@unknown-domain.org"},
                        {"name": "Date", "value": "Mon, 01 Jul 2026 10:30:00 +0000"},
                    ],
                },
            },
            {
                "id": "msg-2",
                "threadId": "thread-2",
                "snippet": "marketing email",
                "payload": {
                    "parts": [{"mimeType": "text/plain", "body": {"data": promo_body}}],
                    "headers": [
                        {"name": "Subject", "value": "Promotional cashback offer"},
                        {"name": "From", "value": "promo@axisbank.com"},
                        {"name": "Date", "value": "Tue, 02 Jul 2026 11:30:00 +0000"},
                    ],
                },
            },
        ]

        response = self.client.post(
            reverse("accounts:gmail_sync"),
            {"gmail_account_id": account.id, "max_results": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["synced_count"], 2)
        self.assertEqual(response.data["ingested_transaction_count"], 0)
        self.assertEqual(response.data["ignored_count"], 2)
        self.assertEqual(BankTransaction.objects.filter(user=self.user).count(), 0)

    @patch("apps.accounts.services.gmail_oauth_service.GmailOAuthService._list_messages")
    @patch("apps.accounts.services.gmail_oauth_service.GmailOAuthService._get_message")
    def test_sync_gmail_keeps_dismissed_discovered_account_dismissed(self, mock_get_message, mock_list_messages) -> None:
        account = GmailAccount.objects.create(
            user=self.user,
            gmail_address="dismissed@gmail.com",
            refresh_token="refresh-sync",
            access_token="access-sync",
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        discovered = DiscoveredAccount.objects.create(
            user=self.user,
            account_number="XXXX1234",
            bank="HDFC",
            account_type="savings",
            status=DiscoveredAccountStatus.DISMISSED,
            supporting_email_count=1,
        )
        body = base64.urlsafe_b64encode(
            b"Your account ending 1234 is debited by INR 450.00 via UPI to chai@oksbi. Ref UTR1234567."
        ).decode("utf-8")

        mock_list_messages.return_value = [{"id": "msg-new-1"}]
        mock_get_message.return_value = {
            "id": "msg-new-1",
            "threadId": "thread-1",
            "snippet": "Debit notification",
            "payload": {
                "parts": [{"mimeType": "text/plain", "body": {"data": body}}],
                "headers": [
                    {"name": "Subject", "value": "UPI Debit Alert"},
                    {"name": "From", "value": "alerts@alerts.hdfcbank.com"},
                    {"name": "Date", "value": "Mon, 01 Jul 2026 10:30:00 +0000"},
                ],
            },
        }

        response = self.client.post(
            reverse("accounts:gmail_sync"),
            {"gmail_account_id": account.id, "max_results": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        discovered.refresh_from_db()
        self.assertEqual(discovered.status, DiscoveredAccountStatus.DISMISSED)
        self.assertEqual(discovered.supporting_email_count, 2)

    def test_list_gmail_accounts(self) -> None:
        GmailAccount.objects.create(
            user=self.user,
            gmail_address="one@gmail.com",
            access_token="access-1",
        )

        response = self.client.get(reverse("accounts:gmail_accounts"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
