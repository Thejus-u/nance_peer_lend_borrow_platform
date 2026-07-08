from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.notifications.models import Notification, NotificationChannel, NotificationStatus
from apps.notifications.services.notification_service import NotificationService


class NotificationServiceTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            mobile_number="+14151110002",
            name="Service User",
            password="StrongPass123!",
        )

    def test_create_notification_defaults_to_pending(self) -> None:
        notification = NotificationService.create_notification(
            user_id=self.user.id,
            channel=NotificationChannel.IN_APP,
            title="Welcome",
            message="Welcome to the platform.",
        )

        self.assertEqual(notification.status, NotificationStatus.PENDING)
        self.assertEqual(notification.user_id, self.user.id)

    def test_create_notification_returns_existing_for_same_dedupe_key(self) -> None:
        first = NotificationService.create_notification(
            user_id=self.user.id,
            channel=NotificationChannel.IN_APP,
            title="Welcome",
            message="Welcome to the platform.",
            dedupe_key="duplicate-key",
        )
        second = NotificationService.create_notification(
            user_id=self.user.id,
            channel=NotificationChannel.IN_APP,
            title="Welcome Again",
            message="Should not duplicate.",
            dedupe_key="duplicate-key",
        )

        self.assertEqual(first.id, second.id)

    def test_mark_sent_updates_status_and_sent_at(self) -> None:
        notification = Notification.objects.create(
            user=self.user,
            channel=NotificationChannel.EMAIL,
            title="Doc",
            message="Please review your document.",
        )

        updated = NotificationService.mark_sent(notification_id=notification.id)

        self.assertEqual(updated.status, NotificationStatus.SENT)
        self.assertIsNotNone(updated.sent_at)

    def test_mark_failed_updates_status_and_reason(self) -> None:
        notification = Notification.objects.create(
            user=self.user,
            channel=NotificationChannel.SMS,
            title="Code",
            message="Your OTP is 1234.",
        )

        updated = NotificationService.mark_failed(
            notification_id=notification.id,
            failed_reason="SMS provider timeout",
        )

        self.assertEqual(updated.status, NotificationStatus.FAILED)
        self.assertEqual(updated.failed_reason, "SMS provider timeout")

    def test_dispatch_pending_notifications_only_sends_due_notifications(self) -> None:
        due_notification = Notification.objects.create(
            user=self.user,
            channel=NotificationChannel.IN_APP,
            title="Now",
            message="Dispatch now",
            scheduled_for=timezone.now() - timedelta(minutes=5),
        )
        future_notification = Notification.objects.create(
            user=self.user,
            channel=NotificationChannel.IN_APP,
            title="Later",
            message="Dispatch later",
            scheduled_for=timezone.now() + timedelta(minutes=30),
        )

        sent_count = NotificationService.dispatch_pending_notifications(limit=10)

        due_notification.refresh_from_db()
        future_notification.refresh_from_db()

        self.assertEqual(sent_count, 1)
        self.assertEqual(due_notification.status, NotificationStatus.SENT)
        self.assertEqual(future_notification.status, NotificationStatus.PENDING)
