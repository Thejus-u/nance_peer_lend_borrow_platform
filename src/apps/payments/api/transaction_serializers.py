from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from rest_framework import serializers

from apps.payments.models import BankTransaction
from apps.payments.services.transaction_service import (
    BankTransactionCreateInput,
    BankTransactionService,
    BankTransactionServiceError,
)


class BankTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankTransaction
        fields = (
            "id",
            "amount",
            "transaction_date",
            "narration",
            "direction",
            "account_number",
            "bank",
            "account_type",
            "source",
            "raw_email_reference_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class BankTransactionCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    transaction_date = serializers.DateTimeField()
    narration = serializers.CharField(required=False, allow_blank=True)
    direction = serializers.CharField(max_length=10)
    account_number = serializers.CharField(max_length=32)
    bank = serializers.CharField(max_length=120)
    account_type = serializers.CharField(max_length=20)

    def save(self, *, user_id: int) -> BankTransaction:
        try:
            payload = BankTransactionCreateInput(
                user_id=user_id,
                amount=Decimal(self.validated_data["amount"]),
                transaction_date=datetime.fromisoformat(self.validated_data["transaction_date"].isoformat()),
                narration=self.validated_data.get("narration", ""),
                direction=self.validated_data["direction"],
                account_number=self.validated_data["account_number"],
                bank=self.validated_data["bank"],
                account_type=self.validated_data["account_type"],
            )
            return BankTransactionService.create_transaction(payload=payload)
        except BankTransactionServiceError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc
