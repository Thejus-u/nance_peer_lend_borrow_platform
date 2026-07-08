from __future__ import annotations

from asgiref.sync import async_to_sync
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.loans.websocket_auth import extract_bearer_token, get_user_for_token


class ChannelsAuthTestCase(TestCase):
    def test_extract_bearer_token_from_query_string(self) -> None:
        scope = {"query_string": b"token=abc123&foo=bar"}
        token = extract_bearer_token(scope)
        self.assertEqual(token, "abc123")

    def test_extract_bearer_token_returns_none_when_missing(self) -> None:
        scope = {"query_string": b"foo=bar"}
        token = extract_bearer_token(scope)
        self.assertIsNone(token)

    def test_get_user_for_valid_token_returns_user(self) -> None:
        user = User.objects.create_user(
            mobile_number="+14158880001",
            name="Socket User",
            password="StrongPass123!",
        )
        token = str(AccessToken.for_user(user))

        resolved_user = async_to_sync(get_user_for_token)(token)

        self.assertEqual(resolved_user.id, user.id)

    def test_get_user_for_invalid_token_returns_anonymous(self) -> None:
        resolved_user = async_to_sync(get_user_for_token)("invalid-token")
        self.assertFalse(resolved_user.is_authenticated)
