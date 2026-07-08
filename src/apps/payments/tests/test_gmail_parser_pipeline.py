from __future__ import annotations

import json
from pathlib import Path

from django.test import TestCase

from apps.payments.services.gmail_parsers.pipeline import GmailTransactionParserPipeline


class GmailParserPipelineTestCase(TestCase):
    def setUp(self) -> None:
        self.pipeline = GmailTransactionParserPipeline()
        fixtures_root = Path(__file__).parent / "fixtures" / "gmail"
        self.savings_samples = json.loads((fixtures_root / "savings_current_samples.json").read_text())
        self.ignored_samples = json.loads((fixtures_root / "credit_card_ignored_samples.json").read_text())

    def test_savings_and_current_fixtures_are_parseable(self) -> None:
        for sample in self.savings_samples:
            result = self.pipeline.parse(subject=sample["subject"], body=sample["body"])
            self.assertFalse(result.ignored)
            self.assertIsNotNone(result.transaction)
            self.assertGreater(result.transaction.amount, 0)
            self.assertIsNotNone(result.transaction.account_hint)

    def test_credit_card_and_promotional_fixtures_are_ignored(self) -> None:
        for sample in self.ignored_samples:
            result = self.pipeline.parse(subject=sample["subject"], body=sample["body"])
            self.assertTrue(result.ignored)
            self.assertIsNone(result.transaction)
