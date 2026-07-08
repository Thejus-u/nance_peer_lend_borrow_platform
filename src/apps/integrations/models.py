from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.integrations.services.token_cipher import decrypt_token, encrypt_token


class GmailAccount(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="integration_gmail_accounts",
    )
    email = models.EmailField(max_length=254, unique=True, db_index=True)
    google_user_id = models.CharField(max_length=255, unique=True)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    connected_at = models.DateTimeField(default=timezone.now)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-connected_at"]
        indexes = [
            models.Index(fields=["user", "connected_at"], name="int_gmail_user_conn_idx"),
            models.Index(fields=["email"], name="int_gmail_email_idx"),
        ]

    def __str__(self) -> str:
        return self.email

    def set_access_token(self, token: str) -> None:
        self.access_token = encrypt_token(token)

    def get_access_token(self) -> str:
        return decrypt_token(self.access_token)

    def set_refresh_token(self, token: str) -> None:
        self.refresh_token = encrypt_token(token)

    def get_refresh_token(self) -> str:
        return decrypt_token(self.refresh_token)


class DiscoveredEmail(models.Model):
    gmail_account = models.ForeignKey(
        GmailAccount,
        on_delete=models.CASCADE,
        related_name="discovered_emails",
    )
    gmail_message_id = models.CharField(max_length=255)
    subject = models.CharField(max_length=500, blank=True)
    sender = models.CharField(max_length=320, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    processed = models.BooleanField(default=False)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["gmail_account", "gmail_message_id"],
                name="int_discovered_email_unique_per_account",
            )
        ]
        indexes = [
            models.Index(fields=["gmail_account", "received_at"], name="int_disc_email_recv_idx"),
            models.Index(fields=["processed"], name="int_disc_email_proc_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.gmail_account_id}:{self.gmail_message_id}"