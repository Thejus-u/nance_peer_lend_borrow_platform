from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


def get_anonymous_user():
    # Import lazily to avoid touching auth models before Django app loading.
    from django.contrib.auth.models import AnonymousUser

    return AnonymousUser()


def extract_bearer_token(scope: dict) -> str | None:
    query_string = scope.get("query_string", b"")
    if not query_string:
        return None

    query_params = parse_qs(query_string.decode("utf-8"), keep_blank_values=False)
    token_values = query_params.get("token")
    if not token_values:
        return None

    token = token_values[0].strip()
    return token or None


@database_sync_to_async
def get_user_for_token(token: str):
    try:
        decoded = AccessToken(token)
    except TokenError:
        return get_anonymous_user()

    user_id = decoded.get("user_id")
    if not user_id:
        return get_anonymous_user()

    user_model = get_user_model()
    try:
        return user_model.objects.get(id=user_id, is_active=True)
    except user_model.DoesNotExist:
        return get_anonymous_user()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        token = extract_bearer_token(scope)
        if token:
            scope["user"] = await get_user_for_token(token)
        else:
            scope["user"] = get_anonymous_user()
        return await super().__call__(scope, receive, send)
