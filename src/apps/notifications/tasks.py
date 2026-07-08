from __future__ import annotations

from celery import shared_task

from apps.notifications.services.notification_service import NotificationService


@shared_task(name="notifications.queue_notification")
def queue_notification_task(
    user_id: int,
    channel: str,
    title: str,
    message: str,
    notification_type: str = "general",
    dedupe_key: str = "",
    payload: dict | None = None,
    scheduled_for: str | None = None,
) -> int:
    notification = NotificationService.create_notification(
        user_id=user_id,
        channel=channel,
        title=title,
        message=message,
        notification_type=notification_type,
        dedupe_key=dedupe_key,
        payload=payload,
        scheduled_for=scheduled_for,
    )
    return notification.id


@shared_task(name="notifications.dispatch_pending")
def dispatch_pending_notifications_task(limit: int = 100) -> int:
    return NotificationService.dispatch_pending_notifications(limit=limit)
