from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Exists, OuterRef

from apps.payments.models import AccountType, DiscoveredAccount, DiscoveredAccountStatus
from apps.payments.models import BankTransaction, TransactionDirection


@dataclass(frozen=True)
class ReconciliationResult:
    matched_transaction: BankTransaction | None
    match_confidence: str | None
    requires_manual_review: bool


class ReconciliationService:
    @staticmethod
    def match_repayment_transaction(
        *,
        user_id: int,
        repayment,
        payment_amount: Decimal,
        paid_at: datetime,
        transaction_reference: str,
    ) -> ReconciliationResult:
        linked_accounts = DiscoveredAccount.objects.filter(
            user_id=user_id,
            status=DiscoveredAccountStatus.LINKED,
            account_number=OuterRef("account_number"),
            bank=OuterRef("bank"),
            account_type=OuterRef("account_type"),
        )

        candidates = BankTransaction.objects.filter(
            user_id=user_id,
            amount=payment_amount,
            direction=TransactionDirection.DEBIT,
            account_type__in=[AccountType.SAVINGS, AccountType.CURRENT],
            transaction_date__gte=paid_at - timedelta(days=5),
            transaction_date__lte=paid_at + timedelta(days=5),
        ).annotate(has_linked_account=Exists(linked_accounts)).filter(
            has_linked_account=True,
        ).order_by("transaction_date")

        best_match = None
        best_confidence = None
        best_score = -1
        normalized_reference = transaction_reference.strip().lower()

        for candidate in candidates:
            score = 0
            narration = (candidate.narration or "").lower()
            if normalized_reference and normalized_reference in narration:
                score += 7

            day_delta = abs((candidate.transaction_date.date() - paid_at.date()).days)
            if day_delta == 0:
                score += 3
            elif day_delta <= 2:
                score += 2
            else:
                score += 1

            if score >= 8:
                confidence = "high"
            elif score >= 4:
                confidence = "medium"
            else:
                confidence = "low"

            if score > best_score:
                best_match = candidate
                best_confidence = confidence
                best_score = score

        if best_match is None:
            return ReconciliationResult(
                matched_transaction=None,
                match_confidence=None,
                requires_manual_review=bool(normalized_reference),
            )

        return ReconciliationResult(
            matched_transaction=best_match,
            match_confidence=best_confidence,
            requires_manual_review=False,
        )