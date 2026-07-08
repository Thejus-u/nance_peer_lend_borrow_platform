from __future__ import annotations

from rest_framework import serializers

from apps.notifications.models import Notification
from apps.notifications.services.notification_service import (
    NotificationService,
    NotificationServiceError,
)


class NotificationSerializer(serializers.ModelSerializer):
    recipient = serializers.IntegerField(source="user_id", read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id",
            "recipient",
            "channel",
            "status",
            "title",
            "message",
            "notification_type",
            "dedupe_key",
            "is_read",
            "payload",
            "scheduled_for",
            "sent_at",
            "failed_reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class NotificationCreateSerializer(serializers.Serializer):
    channel = serializers.CharField(max_length=20)
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
    notification_type = serializers.CharField(max_length=50, required=False, default="general")
    dedupe_key = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    payload = serializers.JSONField(required=False)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)

    def save(self, *, user_id: int) -> Notification:
        try:
            return NotificationService.create_notification(
                user_id=user_id,
                channel=self.validated_data["channel"],
                title=self.validated_data["title"],
                message=self.validated_data["message"],
                notification_type=self.validated_data.get("notification_type", "general"),
                dedupe_key=self.validated_data.get("dedupe_key", ""),
                payload=self.validated_data.get("payload"),
                scheduled_for=self.validated_data.get("scheduled_for"),
            )
        except NotificationServiceError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class NotificationFailSerializer(serializers.Serializer):
    failed_reason = serializers.CharField(max_length=500)

    def save(self, *, notification_id: int) -> Notification:
        try:
            return NotificationService.mark_failed(
                notification_id=notification_id,
                failed_reason=self.validated_data["failed_reason"],
            )
        except NotificationServiceError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc
