from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum

from apps.payments.models import AccountType, BankTransaction, TransactionDirection, TransactionSource


class BankTransactionServiceError(Exception):
    """Base exception for bank transaction operations."""


@dataclass(frozen=True)
class BankTransactionCreateInput:
    user_id: int
    amount: Decimal
    transaction_date: datetime
    narration: str
    direction: str
    account_number: str
    bank: str
    account_type: str
    source: str = TransactionSource.MANUAL
    raw_email_reference_id: str = ""


class BankTransactionService:
    @classmethod
    @transaction.atomic
    def create_transaction(cls, *, payload: BankTransactionCreateInput) -> BankTransaction:
        cls._validate_direction(payload.direction)
        cls._validate_account_type(payload.account_type)
        cls._validate_source(payload.source)

        return BankTransaction.objects.create(
            user_id=payload.user_id,
            amount=payload.amount,
            transaction_date=payload.transaction_date,
            narration=payload.narration,
            direction=payload.direction,
            account_number=payload.account_number,
            bank=payload.bank,
            account_type=payload.account_type,
            source=payload.source,
            raw_email_reference_id=payload.raw_email_reference_id,
        )

    @classmethod
    @transaction.atomic
    def create_transactions_bulk(
        cls,
        *,
        payloads: list[BankTransactionCreateInput],
    ) -> list[BankTransaction]:
        for payload in payloads:
            cls._validate_direction(payload.direction)
            cls._validate_account_type(payload.account_type)
            cls._validate_source(payload.source)

        transactions = [
            BankTransaction(
                user_id=payload.user_id,
                amount=payload.amount,
                transaction_date=payload.transaction_date,
                narration=payload.narration,
                direction=payload.direction,
                account_number=payload.account_number,
                bank=payload.bank,
                account_type=payload.account_type,
                source=payload.source,
                raw_email_reference_id=payload.raw_email_reference_id,
            )
            for payload in payloads
        ]

        for tx in transactions:
            tx.full_clean()

        return BankTransaction.objects.bulk_create(transactions)

    @staticmethod
    def get_user_ledger_summary(*, user_id: int) -> dict[str, Decimal | int]:
        queryset = BankTransaction.objects.filter(user_id=user_id)

        totals = queryset.aggregate(
            total_credit=Sum("amount", filter=Q(direction=TransactionDirection.CREDIT)),
            total_debit=Sum("amount", filter=Q(direction=TransactionDirection.DEBIT)),
            total_count=Count("id"),
        )

        total_credit = totals["total_credit"] or Decimal("0")
        total_debit = totals["total_debit"] or Decimal("0")

        return {
            "total_credit": total_credit,
            "total_debit": total_debit,
            "net": total_credit - total_debit,
            "total_count": totals["total_count"] or 0,
        }

    @staticmethod
    def _validate_direction(direction: str) -> None:
        valid = {choice for choice, _ in TransactionDirection.choices}
        if direction not in valid:
            raise BankTransactionServiceError("Invalid transaction direction.")

    @staticmethod
    def _validate_account_type(account_type: str) -> None:
        valid = {choice for choice, _ in AccountType.choices}
        if account_type not in valid:
            raise BankTransactionServiceError("Invalid account type.")

    @staticmethod
    def _validate_source(source: str) -> None:
        valid = {choice for choice, _ in TransactionSource.choices}
        if source not in valid:
            raise BankTransactionServiceError("Invalid transaction source.")
