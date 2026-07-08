from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.base_user import BaseUserManager

if TYPE_CHECKING:
    from apps.accounts.models import User


class UserManager(BaseUserManager):
    """Manager for mobile-number-first user model."""

    use_in_migrations = True

    def create_user(
        self,
        mobile_number: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> User:
        if not mobile_number:
            raise ValueError("The mobile number must be set.")

        user = self.model(mobile_number=mobile_number, **extra_fields)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        mobile_number: str,
        password: str,
        **extra_fields: object,
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(mobile_number=mobile_number, password=password, **extra_fields)
