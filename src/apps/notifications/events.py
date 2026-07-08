from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from apps.notifications.models import Notification


def publish_notification_event(*, notification: Notification, event: str) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    payload = {
        "type": "notification_event",
        "event": event,
        "timestamp": timezone.now().isoformat(),
        "notification": {
            "id": notification.id,
            "user_id": notification.user_id,
            "status": notification.status,
            "channel": notification.channel,
            "title": notification.title,
            "notification_type": notification.notification_type,
            "created_at": notification.created_at.isoformat() if notification.created_at else None,
        },
    }

    async_to_sync(channel_layer.group_send)(f"loan_user_{notification.user_id}", payload)