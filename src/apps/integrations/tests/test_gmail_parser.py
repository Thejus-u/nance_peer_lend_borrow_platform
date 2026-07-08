from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from django.test import TestCase

from apps.integrations.services.gmail_parser import GmailParserService
from apps.payments.models import AccountType, TransactionDirection


class GmailParserServiceTestCase(TestCase):
    def test_parse_transaction_email_extracts_expected_fields(self) -> None:
        parsed = GmailParserService.parse_transaction_email(
            sender="alerts@alerts.hdfcbank.com",
            subject="UPI Debit Alert",
            body="Your account ending 1234 is debited by INR 450.00 via UPI to chai@oksbi. Ref UTR1234567.",
            received_at=datetime(2026, 7, 8, 10, 30, tzinfo=timezone.utc),
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.amount, Decimal("450.00"))
        self.assertEqual(parsed.account_number, "XXXX1234")
        self.assertEqual(parsed.bank, "HDFC")
        self.assertEqual(parsed.transaction_type, "upi")
        self.assertEqual(parsed.direction, TransactionDirection.DEBIT)
        self.assertEqual(parsed.reference, "UTR1234567")
        self.assertEqual(parsed.account_type, AccountType.SAVINGS)

    def test_parse_transaction_email_returns_none_for_non_bank_sender(self) -> None:
        parsed = GmailParserService.parse_transaction_email(
            sender="hello@example.org",
            subject="UPI Debit Alert",
            body="Your account ending 1234 is debited by INR 450.00 via UPI.",
            received_at=None,
        )

        self.assertIsNone(parsed)