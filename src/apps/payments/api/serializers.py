from __future__ import annotations

from rest_framework import serializers

from apps.payments.models import DiscoveredAccount
from apps.payments.services.discovered_account_service import (
    DiscoveredAccountService,
    DiscoveredAccountServiceError,
)


class DiscoveredAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscoveredAccount
        fields = (
            "id",
            "account_number",
            "bank",
            "account_type",
            "status",
            "first_seen_at",
            "supporting_email_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class DiscoverAccountSerializer(serializers.Serializer):
    account_number = serializers.CharField(max_length=32)
    bank = serializers.CharField(max_length=120)
    account_type = serializers.CharField(max_length=20)

    def save(self, *, user_id: int) -> DiscoveredAccount:
        try:
            return DiscoveredAccountService.discover_account(
                user_id=user_id,
                account_number=self.validated_data["account_number"],
                bank=self.validated_data["bank"],
                account_type=self.validated_data["account_type"],
            )
        except DiscoveredAccountServiceError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class AccountStatusActionSerializer(serializers.Serializer):
    def save(self, *, account_id: int, user_id: int, action: str) -> DiscoveredAccount:
        try:
            if action == "linked":
                return DiscoveredAccountService.link_account(account_id=account_id, user_id=user_id)
            if action == "dismissed":
                return DiscoveredAccountService.dismiss_account(account_id=account_id, user_id=user_id)
            if action == "unlinked":
                return DiscoveredAccountService.unlink_account(account_id=account_id, user_id=user_id)
        except DiscoveredAccountServiceError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc

        raise serializers.ValidationError({"detail": "Unsupported action."})
