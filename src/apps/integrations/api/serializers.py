from __future__ import annotations

from rest_framework import serializers

from apps.integrations.models import DiscoveredEmail, GmailAccount
from apps.integrations.selectors import GmailSelector
from apps.integrations.services.gmail_oauth import GmailOAuthError, GmailOAuthService
from apps.integrations.services.gmail_sync import GmailSyncService


class GmailConnectSerializer(serializers.Serializer):
    redirect_uri = serializers.URLField(max_length=1000)
    frontend_redirect = serializers.URLField(max_length=1000, required=False, allow_null=True, allow_blank=True)

    def build_oauth_url(self, *, user_id: int) -> str:
        return GmailOAuthService.generate_oauth_url(
            user_id=user_id,
            redirect_uri=self.validated_data["redirect_uri"],
            frontend_redirect=self.validated_data.get("frontend_redirect") or None,
        )


class GmailStatusSerializer(serializers.Serializer):
    connected = serializers.BooleanField()
    email = serializers.EmailField(allow_null=True)
    last_sync = serializers.DateTimeField(allow_null=True)
    fetched_email_count = serializers.IntegerField()


class GmailSyncSerializer(serializers.Serializer):
    gmail_account_id = serializers.IntegerField(min_value=1, required=False)
    max_results = serializers.IntegerField(min_value=1, max_value=200, default=20)
    query = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def save(self, *, user_id: int) -> dict[str, int | str | None]:
        try:
            return GmailSyncService.sync_messages(
                user_id=user_id,
                gmail_account_id=self.validated_data.get("gmail_account_id"),
                max_results=self.validated_data["max_results"],
                query=self.validated_data.get("query") or None,
            )
        except (GmailOAuthError, GmailAccount.DoesNotExist) as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class GmailMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscoveredEmail
        fields = (
            "id",
            "gmail_message_id",
            "subject",
            "sender",
            "received_at",
            "processed",
            "created_at",
        )
        read_only_fields = fields


class GmailStatusResponseSerializer(serializers.Serializer):
    @staticmethod
    def from_user(*, user_id: int) -> dict[str, object]:
        return GmailSelector.get_status(user_id=user_id)