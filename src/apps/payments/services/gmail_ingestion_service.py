from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from email.utils import parseaddr

from django.conf import settings
from django.utils import timezone

from apps.audit.services import AuditEventService
from apps.payments.models import (
    AccountType,
    BankTransaction,
    TransactionDirection,
    TransactionSource,
)
from apps.payments.services.discovered_account_service import DiscoveredAccountService
from apps.payments.services.gmail_parsers.pipeline import GmailTransactionParserPipeline
from apps.payments.services.transaction_service import (
    BankTransactionCreateInput,
    BankTransactionService,
)


@dataclass(frozen=True)
class GmailIngestionStats:
    transaction_count: int
    discovered_account_count: int
    ignored_count: int


class GmailIngestionService:
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
    def ingest_message(
        cls,
        *,
        user_id: int,
        gmail_message_id: str,
        sender_email: str,
        subject: str,
        body: str,
        received_at: datetime | None,
    ) -> GmailIngestionStats:
        if not cls._is_whitelisted_sender(sender_email):
            cls._record_email_event(
                user_id=user_id,
                gmail_message_id=gmail_message_id,
                to_state="sender_filtered",
                metadata={"sender_email": sender_email},
            )
            return GmailIngestionStats(transaction_count=0, discovered_account_count=0, ignored_count=1)

        pipeline = GmailTransactionParserPipeline()
        parse_outcome = pipeline.parse(subject=subject, body=body)

        if parse_outcome.ignored:
            cls._record_email_event(
                user_id=user_id,
                gmail_message_id=gmail_message_id,
                to_state="ignored",
                metadata={
                    "sender_email": sender_email,
                    "ignored_category": parse_outcome.ignored_category,
                },
            )
            return GmailIngestionStats(transaction_count=0, discovered_account_count=0, ignored_count=1)

        parsed = parse_outcome.transaction
        if parsed is None:
            cls._record_email_event(
                user_id=user_id,
                gmail_message_id=gmail_message_id,
                to_state="unparsed",
                metadata={"sender_email": sender_email},
            )
            return GmailIngestionStats(transaction_count=0, discovered_account_count=0, ignored_count=0)

        if BankTransaction.objects.filter(
            user_id=user_id,
            source=TransactionSource.GMAIL,
            raw_email_reference_id=gmail_message_id,
        ).exists():
            cls._record_email_event(
                user_id=user_id,
                gmail_message_id=gmail_message_id,
                to_state="duplicate",
                metadata={"sender_email": sender_email},
            )
            return GmailIngestionStats(transaction_count=0, discovered_account_count=0, ignored_count=0)

        account_hint = (parsed.account_hint or "").strip()
        account_number = cls._normalize_account_hint(account_hint) or "XXXX"
        account_type = cls._infer_account_type(subject=subject, body=body)
        bank_name = cls._infer_bank_name(sender_email=sender_email, subject=subject, body=body)
        direction = cls._infer_direction(subject=subject, body=body)

        BankTransactionService.create_transaction(
            payload=BankTransactionCreateInput(
                user_id=user_id,
                amount=Decimal(parsed.amount),
                transaction_date=received_at or timezone.now(),
                narration=parsed.description,
                direction=direction,
                account_number=account_number,
                bank=bank_name,
                account_type=account_type,
                source=TransactionSource.GMAIL,
                raw_email_reference_id=gmail_message_id,
            )
        )

        discovered_before = cls._discovered_account_exists(
            user_id=user_id,
            account_number=account_number,
            bank=bank_name,
            account_type=account_type,
        )

        DiscoveredAccountService.discover_account(
            user_id=user_id,
            account_number=account_number,
            bank=bank_name,
            account_type=account_type,
            increment_supporting_email_count=True,
        )

        cls._record_email_event(
            user_id=user_id,
            gmail_message_id=gmail_message_id,
            to_state="parsed",
            metadata={
                "sender_email": sender_email,
                "bank": bank_name,
                "account_type": account_type,
                "direction": direction,
                "amount": str(parsed.amount),
            },
        )

        return GmailIngestionStats(
            transaction_count=1,
            discovered_account_count=0 if discovered_before else 1,
            ignored_count=0,
        )

    @classmethod
    def extract_plain_text_body(cls, payload: dict) -> str:
        body = cls._decode_message_part(payload.get("payload", {}).get("body", {}))
        if body:
            return body

        for part in payload.get("payload", {}).get("parts", []) or []:
            text = cls._extract_text_from_part(part)
            if text:
                return text

        return payload.get("snippet", "") or ""

    @classmethod
    def _extract_text_from_part(cls, part: dict) -> str:
        mime_type = str(part.get("mimeType", "")).lower()
        if mime_type.startswith("text/plain"):
            return cls._decode_message_part(part.get("body", {}))

        nested_parts = part.get("parts", []) or []
        for nested in nested_parts:
            nested_text = cls._extract_text_from_part(nested)
            if nested_text:
                return nested_text
        return ""

    @staticmethod
    def _decode_message_part(body: dict) -> str:
        data = body.get("data")
        if not data:
            return ""

        padding = "=" * (-len(data) % 4)
        try:
            decoded = base64.urlsafe_b64decode(f"{data}{padding}".encode("utf-8"))
            return decoded.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    @classmethod
    def _is_whitelisted_sender(cls, sender_email: str) -> bool:
        address = parseaddr(sender_email)[1].lower()
        if not address:
            return False

        match = cls._sender_domain_pattern.search(address)
        if not match:
            return False

        domain = match.group(1)
        whitelist = [entry.lower() for entry in settings.GMAIL_BANK_SENDER_DOMAINS]
        return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in whitelist)

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

    @staticmethod
    def _record_email_event(
        *,
        user_id: int,
        gmail_message_id: str,
        to_state: str,
        metadata: dict[str, object],
    ) -> None:
        AuditEventService.record_state_change(
            entity_type="gmail_email",
            entity_id=gmail_message_id,
            field_name="status",
            from_state=None,
            to_state=to_state,
            actor_user_id=user_id,
            metadata=metadata,
        )

    @staticmethod
    def _discovered_account_exists(
        *,
        user_id: int,
        account_number: str,
        bank: str,
        account_type: str,
    ) -> bool:
        from apps.payments.models import DiscoveredAccount

        return DiscoveredAccount.objects.filter(
            user_id=user_id,
            account_number=account_number,
            bank=bank,
            account_type=account_type,
        ).exists()
