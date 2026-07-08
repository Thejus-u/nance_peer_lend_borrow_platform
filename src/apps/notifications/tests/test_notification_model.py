from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.notifications.models import Notification, NotificationChannel, NotificationStatus


class NotificationModelTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            mobile_number="+14151110001",
            name="Model User",
            password="StrongPass123!",
        )

    def test_sent_status_requires_sent_at(self) -> None:
        notification = Notification(
            user=self.user,
            channel=NotificationChannel.IN_APP,
            title="Status Update",
            message="Your loan is approved.",
            status=NotificationStatus.SENT,
            sent_at=None,
        )

        with self.assertRaises(ValidationError):
            notification.full_clean()

    def test_failed_status_requires_reason(self) -> None:
        notification = Notification(
            user=self.user,
            channel=NotificationChannel.SMS,
            title="Delivery Failed",
            message="Could not deliver SMS.",
            status=NotificationStatus.FAILED,
            failed_reason="",
        )

        with self.assertRaises(ValidationError):
            notification.full_clean()

    def test_sent_at_cannot_be_future(self) -> None:
        notification = Notification(
            user=self.user,
            channel=NotificationChannel.EMAIL,
            title="Email Sent",
            message="Your statement is attached.",
            status=NotificationStatus.SENT,
            sent_at=timezone.now() + timedelta(minutes=2),
        )

        with self.assertRaises(ValidationError):
            notification.full_clean()
