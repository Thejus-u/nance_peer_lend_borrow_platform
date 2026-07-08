from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from email.utils import parseaddr

from django.conf import settings

from apps.payments.models import AccountType, TransactionDirection
from apps.payments.services.gmail_parsers.pipeline import GmailTransactionParserPipeline


@dataclass(frozen=True)
class ParsedEmailTransaction:
    date: datetime | None
    amount: Decimal
    account_number: str
    bank: str
    transaction_type: str
    direction: str
    reference: str | None
    description: str
    account_type: str


class GmailParserService:
    _bank_name_patterns: tuple[tuple[str, str], ...] = (
        ("hdfc", "HDFC"),
        ("icici", "ICICI"),
        ("axis", "AXIS"),
        ("sbi", "SBI"),
        ("kotak", "KOTAK"),
        ("yes bank", "YESBANK"),
        ("indusind", "INDUSIND"),
        ("rbl", "RBL"),
    )
    _sender_domain_pattern = re.compile(r"@([A-Za-z0-9.-]+)")

    @classmethod
    def is_bank_sender(cls, sender: str) -> bool:
        address = parseaddr(sender)[1].lower()
        if not address:
            return False
        match = cls._sender_domain_pattern.search(address)
        if not match:
            return False
        domain = match.group(1)
        whitelist = [entry.lower() for entry in settings.GMAIL_BANK_SENDER_DOMAINS]
        return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in whitelist)

    @classmethod
    def parse_transaction_email(
        cls,
        *,
        sender: str,
        subject: str,
        body: str,
        received_at: datetime | None,
    ) -> ParsedEmailTransaction | None:
        if not cls.is_bank_sender(sender):
            return None

        outcome = GmailTransactionParserPipeline().parse(subject=subject, body=body)
        if outcome.ignored or outcome.transaction is None:
            return None

        parsed = outcome.transaction
        return ParsedEmailTransaction(
            date=received_at,
            amount=parsed.amount,
            account_number=cls._normalize_account_hint(parsed.account_hint or ""),
            bank=cls._infer_bank_name(sender_email=sender, subject=subject, body=body),
            transaction_type=parsed.channel,
            direction=cls._infer_direction(subject=subject, body=body),
            reference=parsed.reference_id,
            description=parsed.description,
            account_type=cls._infer_account_type(subject=subject, body=body),
        )

    @staticmethod
    def _normalize_account_hint(account_hint: str) -> str:
        cleaned = account_hint.replace(" ", "").replace("-", "")
        if len(cleaned) >= 4:
            return f"XXXX{cleaned[-4:]}"
        return "XXXX"

    @classmethod
    def _infer_bank_name(cls, *, sender_email: str, subject: str, body: str) -> str:
        text = f"{sender_email} {subject} {body}".lower()
        for pattern, bank_name in cls._bank_name_patterns:
            if pattern in text:
                return bank_name
        return "UNKNOWN"

    @staticmethod
    def _infer_account_type(*, subject: str, body: str) -> str:
        text = f"{subject} {body}".lower()
        if "current" in text:
            return AccountType.CURRENT
        return AccountType.SAVINGS

    @staticmethod
    def _infer_direction(*, subject: str, body: str) -> str:
        text = f"{subject} {body}".lower()
        credit_keywords = ("credited", "credit", "received", "deposit")
        if any(keyword in text for keyword in credit_keywords):
            return TransactionDirection.CREDIT
        return TransactionDirection.DEBIT