from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.loans.models import Loan, Repayment
from apps.loans.services.loan_service import InvalidLoanOperationError, LoanService
from apps.loans.services.repayment_service import (
    InvalidRepaymentOperationError,
    RepaymentService,
)


class LoanSerializer(serializers.ModelSerializer):
    repayment_history = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = (
            "id",
            "public_id",
            "borrower",
            "lender",
            "status",
            "principal_amount",
            "currency",
            "interest_rate",
            "repayment_term_months",
            "starts_at",
            "ends_at",
            "purpose",
            "source_transaction_reference",
            "rejection_reason",
            "repayment_history",
            "submitted_at",
            "approved_at",
            "disbursed_at",
            "closed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_repayment_history(self, obj: Loan) -> list[dict[str, object]]:
        repayments = obj.repayments.order_by("installment_number")
        return [
            {
                "id": repayment.id,
                "installment_number": repayment.installment_number,
                "due_date": repayment.due_date,
                "amount_due": repayment.amount_due,
                "amount_paid": repayment.amount_paid,
                "status": repayment.status,
                "paid_at": repayment.paid_at,
            }
            for repayment in repayments
        ]


class RepaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Repayment
        fields = (
            "id",
            "loan",
            "installment_number",
            "due_date",
            "amount_due",
            "amount_paid",
            "note",
            "transaction_reference",
            "matched_transaction",
            "match_confidence",
            "requires_manual_review",
            "status",
            "paid_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class LoanCreateSerializer(serializers.Serializer):
    borrower_id = serializers.IntegerField(min_value=1, required=False)
    borrower_mobile_number = serializers.CharField(max_length=16, required=False)
    principal_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    repayment_term_months = serializers.IntegerField(min_value=1, max_value=360)
    starts_at = serializers.DateField()
    ends_at = serializers.DateField()
    purpose = serializers.CharField(required=False, allow_blank=True)
    source_transaction_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
    idempotency_key = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs.get("borrower_id") and not attrs.get("borrower_mobile_number"):
            raise serializers.ValidationError(
                {"borrower_mobile_number": "Either borrower_mobile_number or borrower_id is required."}
            )

        idempotency_key = (attrs.get("idempotency_key") or "").strip()
        if not idempotency_key:
            request = self.context.get("request")
            if request is not None:
                idempotency_key = request.headers.get("Idempotency-Key", "").strip()

        if not idempotency_key:
            raise serializers.ValidationError({"idempotency_key": "Idempotency key is required."})

        attrs["idempotency_key"] = idempotency_key
        return attrs

    def create(self, validated_data: dict[str, object]) -> Loan:
        request = self.context["request"]
        try:
            return LoanService.create_loan(
                lender_id=request.user.id,
                borrower_id=validated_data.get("borrower_id"),
                borrower_mobile_number=validated_data.get("borrower_mobile_number"),
                principal_amount=validated_data["principal_amount"],
                currency=str(validated_data["currency"]).upper(),
                interest_rate=validated_data["interest_rate"],
                repayment_term_months=validated_data["repayment_term_months"],
                starts_at=validated_data["starts_at"],
                ends_at=validated_data["ends_at"],
                purpose=validated_data.get("purpose", ""),
                source_transaction_reference=validated_data.get("source_transaction_reference", ""),
                idempotency_key=validated_data["idempotency_key"],
            )
        except InvalidLoanOperationError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class LoanAcceptSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(max_length=255)

    def save(self, *, loan_id: int, borrower_id: int) -> Loan:
        try:
            return LoanService.accept_loan(
                loan_id=loan_id,
                borrower_id=borrower_id,
                idempotency_key=self.validated_data["idempotency_key"],
            )
        except InvalidLoanOperationError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class LoanRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)
    idempotency_key = serializers.CharField(max_length=255)

    def save(self, *, loan_id: int, borrower_id: int) -> Loan:
        try:
            return LoanService.reject_loan(
                loan_id=loan_id,
                borrower_id=borrower_id,
                reason=self.validated_data["reason"],
                idempotency_key=self.validated_data["idempotency_key"],
            )
        except InvalidLoanOperationError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class LoanCancelSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(max_length=255)

    def save(self, *, loan_id: int, requested_by_user_id: int) -> Loan:
        try:
            return LoanService.cancel_loan(
                loan_id=loan_id,
                requested_by_user_id=requested_by_user_id,
                idempotency_key=self.validated_data["idempotency_key"],
            )
        except InvalidLoanOperationError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class RepaymentCreateSerializer(serializers.Serializer):
    installment_number = serializers.IntegerField(min_value=1)
    due_date = serializers.DateField()
    amount_due = serializers.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *, loan_id: int) -> Repayment:
        try:
            return RepaymentService.create_repayment(
                loan_id=loan_id,
                installment_number=self.validated_data["installment_number"],
                due_date=self.validated_data["due_date"],
                amount_due=self.validated_data["amount_due"],
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"detail": "; ".join(exc.messages)}) from exc
        except InvalidRepaymentOperationError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class RepaymentPaySerializer(serializers.Serializer):
    payment_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    paid_at = serializers.DateTimeField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True)
    transaction_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def save(self, *, repayment_id: int) -> Repayment:
        try:
            return RepaymentService.apply_payment(
                repayment_id=repayment_id,
                payment_amount=self.validated_data["payment_amount"],
                paid_at=self.validated_data.get("paid_at"),
                note=self.validated_data.get("note", ""),
                transaction_reference=self.validated_data.get("transaction_reference", ""),
            )
        except InvalidRepaymentOperationError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc
