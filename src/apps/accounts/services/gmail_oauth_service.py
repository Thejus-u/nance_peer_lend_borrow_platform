from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib import parse, request

from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_timezone

from apps.accounts.models import GmailAccount, GmailSyncedEmail, User
from apps.payments.services.gmail_ingestion_service import GmailIngestionService


class GmailOAuthServiceError(Exception):
    """Base exception for Gmail OAuth operations."""


class InvalidGmailOAuthOperationError(GmailOAuthServiceError):
    """Raised when Gmail OAuth operation cannot be completed."""


@dataclass(frozen=True)
class TokenPayload:
    access_token: str
    refresh_token: str | None
    expires_in: int
    scope: str


@dataclass(frozen=True)
class GmailProfile:
    email: str
    sub: str


class GmailOAuthService:
    @classmethod
    @transaction.atomic
    def connect_gmail(
        cls,
        *,
        user: User,
        authorization_code: str,
        redirect_uri: str,
        set_primary: bool,
    ) -> GmailAccount:
        token_payload = cls._exchange_auth_code(
            authorization_code=authorization_code,
            redirect_uri=redirect_uri,
        )
        profile = cls._fetch_gmail_profile(access_token=token_payload.access_token)

        existing_for_other_user = GmailAccount.objects.select_for_update().filter(
            gmail_address=profile.email
        ).exclude(user_id=user.id)
        if existing_for_other_user.exists():
            raise InvalidGmailOAuthOperationError(
                "This Gmail account is already connected to another user."
            )

        account, _ = GmailAccount.objects.select_for_update().get_or_create(
            user=user,
            gmail_address=profile.email,
            defaults={
                "is_verified": True,
            },
        )

        if set_primary:
            GmailAccount.objects.filter(user=user, is_primary=True).update(is_primary=False)
            account.is_primary = True
        elif not GmailAccount.objects.filter(user=user, is_primary=True).exclude(id=account.id).exists():
            account.is_primary = True

        account.google_sub = profile.sub
        account.access_token = token_payload.access_token
        if token_payload.refresh_token:
            account.refresh_token = token_payload.refresh_token
        account.token_scopes = token_payload.scope
        account.token_expires_at = django_timezone.now() + timedelta(seconds=token_payload.expires_in)
        account.is_verified = True
        account.save(
            update_fields=[
                "is_primary",
                "google_sub",
                "access_token",
                "refresh_token",
                "token_scopes",
                "token_expires_at",
                "is_verified",
                "updated_at",
            ]
        )
        return account

    @classmethod
    @transaction.atomic
    def refresh_token(cls, *, user: User, gmail_account_id: int) -> GmailAccount:
        account = GmailAccount.objects.select_for_update().get(id=gmail_account_id, user=user)

        if not account.refresh_token:
            raise InvalidGmailOAuthOperationError(
                "Refresh token is unavailable for this Gmail account."
            )

        token_payload = cls._refresh_access_token(refresh_token=account.refresh_token)

        account.access_token = token_payload.access_token
        if token_payload.refresh_token:
            account.refresh_token = token_payload.refresh_token
        account.token_scopes = token_payload.scope
        account.token_expires_at = django_timezone.now() + timedelta(seconds=token_payload.expires_in)
        account.save(update_fields=["access_token", "refresh_token", "token_scopes", "token_expires_at", "updated_at"])
        return account

    @classmethod
    @transaction.atomic
    def sync_emails(
        cls,
        *,
        user: User,
        gmail_account_id: int,
        max_results: int,
        query: str | None,
    ) -> dict[str, int]:
        account = GmailAccount.objects.select_for_update().get(id=gmail_account_id, user=user)
        cls._ensure_access_token(account=account)

        messages = cls._list_messages(
            access_token=account.access_token,
            max_results=max_results,
            query=query,
        )

        synced_count = 0
        ingested_transaction_count = 0
        discovered_account_count = 0
        ignored_count = 0
        for message in messages:
            payload = cls._get_message(access_token=account.access_token, message_id=message["id"])
            metadata = cls._extract_metadata(payload)
            body_text = GmailIngestionService.extract_plain_text_body(payload)

            _, created = GmailSyncedEmail.objects.update_or_create(
                gmail_account=account,
                gmail_message_id=message["id"],
                defaults={
                    "thread_id": payload.get("threadId", ""),
                    "subject": metadata.get("subject", ""),
                    "sender_email": metadata.get("from", ""),
                    "snippet": payload.get("snippet", ""),
                    "received_at": metadata.get("received_at"),
                },
            )
            synced_count += 1

            if created:
                stats = GmailIngestionService.ingest_message(
                    user_id=user.id,
                    gmail_message_id=message["id"],
                    sender_email=metadata.get("from", ""),
                    subject=metadata.get("subject", ""),
                    body=body_text,
                    received_at=metadata.get("received_at"),
                )
                ingested_transaction_count += stats.transaction_count
                discovered_account_count += stats.discovered_account_count
                ignored_count += stats.ignored_count

        account.last_synced_at = django_timezone.now()
        account.save(update_fields=["last_synced_at", "updated_at"])

        return {
            "synced_count": synced_count,
            "ingested_transaction_count": ingested_transaction_count,
            "discovered_account_count": discovered_account_count,
            "ignored_count": ignored_count,
        }

    @classmethod
    def _ensure_access_token(cls, *, account: GmailAccount) -> None:
        if not account.access_token:
            raise InvalidGmailOAuthOperationError("Access token is missing for this Gmail account.")

        if account.token_expires_at and account.token_expires_at <= django_timezone.now():
            if not account.refresh_token:
                raise InvalidGmailOAuthOperationError("Gmail access token expired and no refresh token is available.")
            refreshed = cls._refresh_access_token(refresh_token=account.refresh_token)
            account.access_token = refreshed.access_token
            if refreshed.refresh_token:
                account.refresh_token = refreshed.refresh_token
            account.token_scopes = refreshed.scope
            account.token_expires_at = django_timezone.now() + timedelta(seconds=refreshed.expires_in)
            account.save(update_fields=["access_token", "refresh_token", "token_scopes", "token_expires_at", "updated_at"])

    @classmethod
    def _exchange_auth_code(cls, *, authorization_code: str, redirect_uri: str) -> TokenPayload:
        if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_CLIENT_SECRET:
            raise InvalidGmailOAuthOperationError("Gmail OAuth client credentials are not configured.")

        response = cls._http_post_form(
            settings.GMAIL_TOKEN_URL,
            {
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "code": authorization_code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        return cls._build_token_payload(response)

    @classmethod
    def _refresh_access_token(cls, *, refresh_token: str) -> TokenPayload:
        if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_CLIENT_SECRET:
            raise InvalidGmailOAuthOperationError("Gmail OAuth client credentials are not configured.")

        response = cls._http_post_form(
            settings.GMAIL_TOKEN_URL,
            {
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        return cls._build_token_payload(response)

    @classmethod
    def _fetch_gmail_profile(cls, *, access_token: str) -> GmailProfile:
        profile_json = cls._http_get_json(
            settings.GMAIL_USERINFO_URL,
            access_token=access_token,
        )
        email = profile_json.get("email")
        sub = profile_json.get("sub")
        if not email or not sub:
            raise InvalidGmailOAuthOperationError("Google profile response is missing required fields.")
        return GmailProfile(email=email.lower(), sub=sub)

    @classmethod
    def _list_messages(cls, *, access_token: str, max_results: int, query: str | None) -> list[dict[str, str]]:
        params = {"maxResults": str(max(1, min(max_results, 200)))}
        if query:
            params["q"] = query

        endpoint = f"{settings.GMAIL_MESSAGES_LIST_URL}?{parse.urlencode(params)}"
        response = cls._http_get_json(endpoint, access_token=access_token)
        return response.get("messages", [])

    @classmethod
    def _get_message(cls, *, access_token: str, message_id: str) -> dict:
        endpoint = f"{settings.GMAIL_MESSAGES_GET_URL}/{message_id}?format=full&metadataHeaders=Subject&metadataHeaders=From&metadataHeaders=Date"
        return cls._http_get_json(endpoint, access_token=access_token)

    @staticmethod
    def _extract_metadata(message_payload: dict) -> dict[str, datetime | str | None]:
        headers = message_payload.get("payload", {}).get("headers", [])
        data = {"subject": "", "from": "", "received_at": None}
        for header in headers:
            name = str(header.get("name", "")).lower()
            value = str(header.get("value", "")).strip()
            if name == "subject":
                data["subject"] = value
            elif name == "from":
                data["from"] = value
            elif name == "date":
                try:
                    parsed = datetime.strptime(value[:31], "%a, %d %b %Y %H:%M:%S %z")
                    data["received_at"] = parsed.astimezone(timezone.utc)
                except ValueError:
                    data["received_at"] = None
        return data

    @staticmethod
    def _build_token_payload(raw: dict) -> TokenPayload:
        access_token = raw.get("access_token")
        if not access_token:
            raise InvalidGmailOAuthOperationError("Google token response does not contain access_token.")

        expires_in = int(raw.get("expires_in", 3600))
        return TokenPayload(
            access_token=access_token,
            refresh_token=raw.get("refresh_token"),
            expires_in=expires_in,
            scope=raw.get("scope", ""),
        )

    @staticmethod
    def _http_post_form(url: str, payload: dict[str, str]) -> dict:
        encoded = parse.urlencode(payload).encode("utf-8")
        req = request.Request(url, data=encoded, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with request.urlopen(req, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover
            raise InvalidGmailOAuthOperationError("Failed to call Gmail OAuth token endpoint.") from exc

    @staticmethod
    def _http_get_json(url: str, *, access_token: str) -> dict:
        req = request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {access_token}")

        try:
            with request.urlopen(req, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover
            raise InvalidGmailOAuthOperationError("Failed to call Gmail API.") from exc
