from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Pattern


@dataclass(frozen=True)
class ParsedTransaction:
    channel: str
    amount: Decimal
    currency: str
    description: str
    reference_id: str | None = None
    account_hint: str | None = None
    counterparty: str | None = None


class BaseGmailParser(ABC):
    """Base contract for transaction email parsers."""

    amount_pattern: Pattern[str] = re.compile(
        r"(?:INR|Rs\.?|\u20b9)\s*([0-9,]+(?:\.[0-9]{1,2})?)",
        re.IGNORECASE,
    )
    reference_pattern: Pattern[str] = re.compile(
        r"(?:UTR|Ref(?:erence)?|Txn(?:\s*ID)?)\s*[:\-]?\s*([A-Za-z0-9\-]{6,})",
        re.IGNORECASE,
    )
    account_pattern: Pattern[str] = re.compile(
        r"(?:A/C|Account|Acct|ending with|ending)\s*[:\-]?\s*([Xx*0-9]{2,})",
        re.IGNORECASE,
    )

    @property
    @abstractmethod
    def channel(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def can_parse(self, subject: str, body: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, subject: str, body: str) -> ParsedTransaction:
        raise NotImplementedError

    def extract_amount(self, text: str) -> Decimal:
        match = self.amount_pattern.search(text)
        if not match:
            raise ValueError("Amount not found in email content.")

        normalized = match.group(1).replace(",", "").strip()
        try:
            return Decimal(normalized)
        except InvalidOperation as exc:
            raise ValueError("Amount format is invalid.") from exc

    def extract_reference_id(self, text: str) -> str | None:
        match = self.reference_pattern.search(text)
        return match.group(1) if match else None

    def extract_account_hint(self, text: str) -> str | None:
        match = self.account_pattern.search(text)
        return match.group(1) if match else None

    def compact_description(self, subject: str, body: str) -> str:
        summary = f"{subject.strip()} | {body.strip()}"
        return re.sub(r"\s+", " ", summary)[:240]
