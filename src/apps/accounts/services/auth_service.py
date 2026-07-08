from __future__ import annotations

from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import GmailAccount, User


@transaction.atomic
def register_user(
    *,
    mobile_number: str,
    name: str,
    password: str,
    gmail_address: str | None = None,
    profile_image=None,
) -> User:
    """Create a user and optional primary Gmail account atomically."""
    user = User.objects.select_for_update().filter(mobile_number=mobile_number).first()

    if user is None:
        user = User.objects.create_user(
            mobile_number=mobile_number,
            name=name,
            password=password,
            profile_image=profile_image,
        )
    else:
        if user.is_active or user.has_usable_password():
            raise ValueError("A user with this mobile number already exists.")

        user.name = name
        user.profile_image = profile_image
        user.is_active = True
        user.set_password(password)
        user.full_clean()
        user.save(update_fields=["name", "profile_image", "is_active", "password", "updated_at"])

    if gmail_address:
        GmailAccount.objects.update_or_create(
            user=user,
            gmail_address=gmail_address,
            defaults={"is_primary": True},
        )

    return user


def blacklist_refresh_token(*, refresh_token: str) -> None:
    """Blacklist a refresh token to invalidate future token refresh calls."""
    token = RefreshToken(refresh_token)
    token.blacklist()
