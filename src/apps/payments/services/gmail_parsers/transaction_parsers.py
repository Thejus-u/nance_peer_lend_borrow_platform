from __future__ import annotations

import re
from decimal import Decimal

from apps.payments.services.gmail_parsers.base import BaseGmailParser, ParsedTransaction


class UPIParser(BaseGmailParser):
    channel = "upi"
    _keywords = ("upi", "vpa", "collect request", "upi txn")
    _counterparty_pattern = re.compile(
        r"(?:to|from)\s+([A-Za-z0-9@._\- ]{3,80})",
        re.IGNORECASE,
    )

    def can_parse(self, subject: str, body: str) -> bool:
        text = f"{subject} {body}".lower()
        return any(keyword in text for keyword in self._keywords)

    def parse(self, subject: str, body: str) -> ParsedTransaction:
        text = f"{subject}\n{body}"
        counterparty = None
        match = self._counterparty_pattern.search(text)
        if match:
            counterparty = match.group(1).strip()

        return ParsedTransaction(
            channel=self.channel,
            amount=self.extract_amount(text),
            currency="INR",
            description=self.compact_description(subject, body),
            reference_id=self.extract_reference_id(text),
            account_hint=self.extract_account_hint(text),
            counterparty=counterparty,
        )


class NEFTParser(BaseGmailParser):
    channel = "neft"
    _keywords = ("neft", "national electronic funds transfer")

    def can_parse(self, subject: str, body: str) -> bool:
        text = f"{subject} {body}".lower()
        return any(keyword in text for keyword in self._keywords)

    def parse(self, subject: str, body: str) -> ParsedTransaction:
        text = f"{subject}\n{body}"
        return ParsedTransaction(
            channel=self.channel,
            amount=self.extract_amount(text),
            currency="INR",
            description=self.compact_description(subject, body),
            reference_id=self.extract_reference_id(text),
            account_hint=self.extract_account_hint(text),
        )


class RTGSParser(BaseGmailParser):
    channel = "rtgs"
    _keywords = ("rtgs", "real time gross settlement")

    def can_parse(self, subject: str, body: str) -> bool:
        text = f"{subject} {body}".lower()
        return any(keyword in text for keyword in self._keywords)

    def parse(self, subject: str, body: str) -> ParsedTransaction:
        text = f"{subject}\n{body}"
        return ParsedTransaction(
            channel=self.channel,
            amount=self.extract_amount(text),
            currency="INR",
            description=self.compact_description(subject, body),
            reference_id=self.extract_reference_id(text),
            account_hint=self.extract_account_hint(text),
        )


class ATMParser(BaseGmailParser):
    channel = "atm"
    _keywords = ("atm", "cash withdrawal", "cash deposit")

    def can_parse(self, subject: str, body: str) -> bool:
        text = f"{subject} {body}".lower()
        return any(keyword in text for keyword in self._keywords)

    def parse(self, subject: str, body: str) -> ParsedTransaction:
        text = f"{subject}\n{body}"
        return ParsedTransaction(
            channel=self.channel,
            amount=self.extract_amount(text),
            currency="INR",
            description=self.compact_description(subject, body),
            reference_id=self.extract_reference_id(text),
            account_hint=self.extract_account_hint(text),
        )


class DebitParser(BaseGmailParser):
    channel = "debit"
    _keywords = ("debited", "debit", "withdrawn", "sent")

    def can_parse(self, subject: str, body: str) -> bool:
        text = f"{subject} {body}".lower()
        return any(keyword in text for keyword in self._keywords)

    def parse(self, subject: str, body: str) -> ParsedTransaction:
        text = f"{subject}\n{body}"
        return ParsedTransaction(
            channel=self.channel,
            amount=self.extract_amount(text),
            currency="INR",
            description=self.compact_description(subject, body),
            reference_id=self.extract_reference_id(text),
            account_hint=self.extract_account_hint(text),
        )


class CreditParser(BaseGmailParser):
    channel = "credit"
    _keywords = ("credited", "credit", "received")

    def can_parse(self, subject: str, body: str) -> bool:
        text = f"{subject} {body}".lower()
        return any(keyword in text for keyword in self._keywords)

    def parse(self, subject: str, body: str) -> ParsedTransaction:
        text = f"{subject}\n{body}"
        return ParsedTransaction(
            channel=self.channel,
            amount=self.extract_amount(text),
            currency="INR",
            description=self.compact_description(subject, body),
            reference_id=self.extract_reference_id(text),
            account_hint=self.extract_account_hint(text),
        )
