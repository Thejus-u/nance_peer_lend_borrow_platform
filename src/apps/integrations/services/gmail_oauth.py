from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from urllib import parse, request

from django.conf import settings
from django.core import signing
from django.utils import timezone

from apps.accounts.models import User
from apps.integrations.models import GmailAccount


class GmailOAuthError(Exception):
    """Raised when OAuth flow fails."""


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
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    STATE_SALT = "integrations.gmail.oauth"
    SCOPES = (
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/gmail.readonly",
    )

    @classmethod
    def generate_oauth_url(
        cls,
        *,
        user_id: int,
        redirect_uri: str,
        frontend_redirect: str | None,
    ) -> str:
        state = signing.dumps(
            {
                "user_id": user_id,
                "redirect_uri": redirect_uri,
                "frontend_redirect": frontend_redirect,
            },
            salt=cls.STATE_SALT,
        )
        params = {
            "client_id": settings.GMAIL_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(cls.SCOPES),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
        return f"{cls.AUTH_URL}?{parse.urlencode(params)}"

    @classmethod
    def connect_from_callback(cls, *, authorization_code: str, state_token: str) -> tuple[GmailAccount, str | None]:
        state = cls._load_state(state_token=state_token)
        user = User.objects.get(id=state["user_id"])
        token_payload = cls._exchange_auth_code(
            authorization_code=authorization_code,
            redirect_uri=state["redirect_uri"],
        )
        profile = cls._fetch_gmail_profile(access_token=token_payload.access_token)

        existing_for_other_user = GmailAccount.objects.filter(email=profile.email).exclude(user_id=user.id)
        if existing_for_other_user.exists():
            raise GmailOAuthError("This Gmail account is already connected to another user.")

        account, _ = GmailAccount.objects.get_or_create(
            user=user,
            email=profile.email,
            defaults={
                "google_user_id": profile.sub,
            },
        )
        account.google_user_id = profile.sub
        account.set_access_token(token_payload.access_token)
        if token_payload.refresh_token:
            account.set_refresh_token(token_payload.refresh_token)
        account.expires_at = timezone.now() + timedelta(seconds=token_payload.expires_in)
        account.save()
        return account, state.get("frontend_redirect")

    @classmethod
    def ensure_access_token(cls, *, account: GmailAccount) -> GmailAccount:
        access_token = account.get_access_token()
        if not access_token:
            raise GmailOAuthError("Access token is missing for this Gmail account.")

        if account.expires_at and account.expires_at <= timezone.now():
            refresh_token = account.get_refresh_token()
            if not refresh_token:
                raise GmailOAuthError("Gmail access token expired and no refresh token is available.")
            payload = cls._refresh_access_token(refresh_token=refresh_token)
            account.set_access_token(payload.access_token)
            if payload.refresh_token:
                account.set_refresh_token(payload.refresh_token)
            account.expires_at = timezone.now() + timedelta(seconds=payload.expires_in)
            account.save(update_fields=["access_token", "refresh_token", "expires_at", "updated_at"])
        return account

    @classmethod
    def _load_state(cls, *, state_token: str) -> dict[str, object]:
        try:
            return signing.loads(state_token, salt=cls.STATE_SALT, max_age=60 * 15)
        except signing.BadSignature as exc:
            raise GmailOAuthError("OAuth callback state is invalid or expired.") from exc

    @classmethod
    def _exchange_auth_code(cls, *, authorization_code: str, redirect_uri: str) -> TokenPayload:
        if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_CLIENT_SECRET:
            raise GmailOAuthError("Gmail OAuth client credentials are not configured.")

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
            raise GmailOAuthError("Gmail OAuth client credentials are not configured.")

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
        profile_json = cls._http_get_json(settings.GMAIL_USERINFO_URL, access_token=access_token)
        email = str(profile_json.get("email", "")).lower()
        sub = str(profile_json.get("sub", ""))
        if not email or not sub:
            raise GmailOAuthError("Google profile response is missing required fields.")
        return GmailProfile(email=email, sub=sub)

    @staticmethod
    def _build_token_payload(raw: dict) -> TokenPayload:
        access_token = raw.get("access_token")
        if not access_token:
            raise GmailOAuthError("Google token response does not contain access_token.")

        return TokenPayload(
            access_token=access_token,
            refresh_token=raw.get("refresh_token"),
            expires_in=int(raw.get("expires_in", 3600)),
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
            raise GmailOAuthError("Failed to call Gmail OAuth token endpoint.") from exc

    @staticmethod
    def _http_get_json(url: str, *, access_token: str) -> dict:
        req = request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {access_token}")
        try:
            with request.urlopen(req, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover
            raise GmailOAuthError("Failed to call Gmail user profile endpoint.") from exc