from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class NotificationChannel(models.TextChoices):
    IN_APP = "in_app", "In App"
    SMS = "sms", "SMS"
    EMAIL = "email", "Email"


class NotificationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, default="general", db_index=True)
    dedupe_key = models.CharField(max_length=255, blank=True, default="", db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    failed_reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_for"], name="notif_status_sched_idx"),
            models.Index(fields=["user", "status"], name="notif_user_status_idx"),
            models.Index(fields=["user", "is_read"], name="notif_user_read_idx"),
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}

        if self.status == NotificationStatus.SENT and not self.sent_at:
            errors["sent_at"] = "sent_at is required when notification status is sent."

        if self.status == NotificationStatus.FAILED and not self.failed_reason.strip():
            errors["failed_reason"] = "failed_reason is required when notification status is failed."

        if self.status != NotificationStatus.FAILED and self.failed_reason:
            errors["failed_reason"] = "failed_reason can only be set for failed notifications."

        if self.sent_at and self.sent_at > timezone.now():
            errors["sent_at"] = "sent_at cannot be in the future."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user_id}:{self.channel}:{self.status}"
