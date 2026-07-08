from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import User
from apps.loans.services.loan_service import LoanService


class LoanServiceEventsTestCase(TestCase):
    def setUp(self) -> None:
        self.lender = User.objects.create_user(
            mobile_number="+14158880004",
            name="Lender Events",
            password="StrongPass123!",
        )
        self.borrower = User.objects.create_user(
            mobile_number="+14158880005",
            name="Borrower Events",
            password="StrongPass123!",
        )

    @patch("apps.loans.services.loan_service.publish_loan_event")
    def test_create_loan_emits_created_event(self, mocked_publish) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            LoanService.create_loan(
                lender_id=self.lender.id,
                borrower_id=self.borrower.id,
                principal_amount=Decimal("1200.00"),
                currency="USD",
                interest_rate=Decimal("8.50"),
                repayment_term_months=12,
                starts_at=date.today(),
                ends_at=date.today() + timedelta(days=365),
                purpose="Event emission",
                idempotency_key="event-test-key-1",
            )

        self.assertTrue(mocked_publish.called)
        args = mocked_publish.call_args.kwargs
        self.assertEqual(args["event"], "loan.created")
        self.assertEqual(args["actor_user_id"], self.lender.id)
