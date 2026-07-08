from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.audit.services import AuditEventService
from apps.notifications.events import publish_notification_event
from apps.notifications.models import Notification, NotificationStatus


class NotificationServiceError(Exception):
    """Base service-layer exception for notifications."""


class NotificationService:
    @classmethod
    @transaction.atomic
    def create_notification(
        cls,
        *,
        user_id: int,
        channel: str,
        title: str,
        message: str,
        notification_type: str = "general",
        dedupe_key: str = "",
        payload: dict[str, Any] | None = None,
        scheduled_for=None,
    ) -> Notification:
        normalized_dedupe_key = dedupe_key.strip()
        if normalized_dedupe_key:
            existing = Notification.objects.filter(
                user_id=user_id,
                dedupe_key=normalized_dedupe_key,
            ).order_by("-created_at").first()
            if existing is not None:
                return existing

        notification = Notification.objects.create(
            user_id=user_id,
            channel=channel,
            title=title,
            message=message,
            notification_type=notification_type,
            dedupe_key=normalized_dedupe_key,
            payload=payload or {},
            scheduled_for=scheduled_for,
            status=NotificationStatus.PENDING,
        )
        AuditEventService.record_state_change(
            entity_type="notification",
            entity_id=notification.id,
            field_name="status",
            from_state=None,
            to_state=notification.status,
            actor_user_id=user_id,
            metadata={"action": "notification.create"},
        )
        transaction.on_commit(
            lambda: publish_notification_event(notification=notification, event="notification.created")
        )

        def dispatch_pending_notifications() -> None:
            from apps.notifications.tasks import dispatch_pending_notifications_task

            dispatch_pending_notifications_task.delay(limit=100)

        transaction.on_commit(dispatch_pending_notifications)
        return notification

    @classmethod
    @transaction.atomic
    def mark_sent(cls, *, notification_id: int) -> Notification:
        notification = cls._get_notification_for_update(notification_id=notification_id)
        previous_status = notification.status
        notification.status = NotificationStatus.SENT
        notification.sent_at = timezone.now()
        notification.failed_reason = ""
        notification.save(update_fields=["status", "sent_at", "failed_reason", "updated_at"])
        cls._record_status_change(
            notification=notification,
            from_status=previous_status,
            action="notification.mark_sent",
        )
        transaction.on_commit(
            lambda: publish_notification_event(notification=notification, event="notification.sent")
        )
        return notification

    @classmethod
    @transaction.atomic
    def mark_failed(cls, *, notification_id: int, failed_reason: str) -> Notification:
        notification = cls._get_notification_for_update(notification_id=notification_id)
        previous_status = notification.status
        notification.status = NotificationStatus.FAILED
        notification.failed_reason = failed_reason.strip()
        notification.sent_at = None
        notification.save(update_fields=["status", "failed_reason", "sent_at", "updated_at"])
        cls._record_status_change(
            notification=notification,
            from_status=previous_status,
            action="notification.mark_failed",
            metadata={"failed_reason": notification.failed_reason},
        )
        transaction.on_commit(
            lambda: publish_notification_event(notification=notification, event="notification.failed")
        )
        return notification

    @classmethod
    def dispatch_pending_notifications(cls, *, limit: int = 100) -> int:
        now = timezone.now()
        pending: QuerySet[Notification] = (
            Notification.objects.filter(status=NotificationStatus.PENDING)
            .filter(Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=now))
            .order_by("created_at")[:limit]
        )

        sent_count = 0
        for notification in pending:
            cls.mark_sent(notification_id=notification.id)
            sent_count += 1
        return sent_count

    @staticmethod
    def _get_notification_for_update(*, notification_id: int) -> Notification:
        try:
            return Notification.objects.select_for_update().get(id=notification_id)
        except Notification.DoesNotExist as exc:
            raise NotificationServiceError("Notification not found.") from exc

    @staticmethod
    def _record_status_change(
        *,
        notification: Notification,
        from_status: str | None,
        action: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if from_status == notification.status:
            return

        payload = {"action": action}
        if metadata:
            payload.update(metadata)

        AuditEventService.record_state_change(
            entity_type="notification",
            entity_id=notification.id,
            field_name="status",
            from_state=from_status,
            to_state=notification.status,
            actor_user_id=notification.user_id,
            metadata=payload,
        )
