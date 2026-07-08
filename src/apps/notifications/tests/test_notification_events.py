from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TestCase

from apps.accounts.models import User
from apps.notifications.events import publish_notification_event
from apps.notifications.models import Notification


class NotificationEventsTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            mobile_number="+14152220001",
            name="Notification Socket",
            password="StrongPass123!",
        )
        self.notification = Notification.objects.create(
            user=self.user,
            channel="in_app",
            title="Socket",
            message="Socket message",
            notification_type="general",
        )

    @patch("apps.notifications.events.get_channel_layer")
    def test_publish_notification_event_sends_to_user_group(self, mocked_get_channel_layer) -> None:
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mocked_get_channel_layer.return_value = fake_layer

        publish_notification_event(notification=self.notification, event="notification.created")

        fake_layer.group_send.assert_called_once()
        called_group = fake_layer.group_send.call_args.args[0]
        self.assertEqual(called_group, f"loan_user_{self.user.id}")
