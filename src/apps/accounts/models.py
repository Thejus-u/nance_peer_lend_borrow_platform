from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.accounts.managers import UserManager
from apps.accounts.validators import validate_gmail_address, validate_mobile_number


class User(AbstractBaseUser, PermissionsMixin):
    """Core platform user identified by mobile number."""

    mobile_number = models.CharField(
        max_length=16,
        unique=True,
        validators=[validate_mobile_number],
        db_index=True,
    )
    name = models.CharField(max_length=255)
    profile_image = models.ImageField(upload_to="users/profile-images/", blank=True, null=True)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "mobile_number"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return f"{self.name} ({self.mobile_number})"


class GmailAccount(models.Model):
    """Linked Gmail identities for a platform user."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="gmail_accounts")
    gmail_address = models.EmailField(max_length=254, unique=True, validators=[validate_gmail_address])
    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_scopes = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_primary"], name="gmail_account_user_primary_idx"),
            models.Index(fields=["gmail_address"], name="gmail_account_address_idx"),
        ]

    def __str__(self) -> str:
        return self.gmail_address


class GmailSyncedEmail(models.Model):
    gmail_account = models.ForeignKey(
        GmailAccount,
        on_delete=models.CASCADE,
        related_name="synced_emails",
    )
    gmail_message_id = models.CharField(max_length=255)
    thread_id = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=500, blank=True)
    sender_email = models.EmailField(max_length=254, blank=True)
    snippet = models.TextField(blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at", "-synced_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["gmail_account", "gmail_message_id"],
                name="gmail_synced_email_unique_per_account",
            )
        ]
        indexes = [
            models.Index(fields=["gmail_account", "received_at"], name="gmail_email_acc_recv_idx"),
            models.Index(fields=["gmail_message_id"], name="gmail_email_message_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.gmail_account_id}:{self.gmail_message_id}"
