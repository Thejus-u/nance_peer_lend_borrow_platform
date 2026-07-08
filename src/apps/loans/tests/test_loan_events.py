from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TestCase

from apps.accounts.models import User
from apps.loans.choices import LoanStatus
from apps.loans.events import publish_loan_event
from apps.loans.models import Loan


class LoanEventsTestCase(TestCase):
    def setUp(self) -> None:
        self.borrower = User.objects.create_user(
            mobile_number="+14158880002",
            name="Borrower Socket",
            password="StrongPass123!",
        )
        self.lender = User.objects.create_user(
            mobile_number="+14158880003",
            name="Lender Socket",
            password="StrongPass123!",
        )
        self.loan = Loan.objects.create(
            borrower=self.borrower,
            lender=self.lender,
            status=LoanStatus.PENDING_REVIEW,
            principal_amount="500.00",
            currency="USD",
            interest_rate="5.00",
            repayment_term_months=6,
            starts_at=date.today(),
            ends_at=date.today() + timedelta(days=180),
            purpose="Socket event test",
        )

    @patch("apps.loans.events.get_channel_layer")
    def test_publish_loan_event_sends_to_expected_groups(self, mocked_get_channel_layer) -> None:
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mocked_get_channel_layer.return_value = fake_layer

        publish_loan_event(loan=self.loan, event="loan.created", actor_user_id=self.borrower.id)

        called_groups = {call.args[0] for call in fake_layer.group_send.call_args_list}
        self.assertIn(f"loan_{self.loan.id}", called_groups)
        self.assertIn(f"loan_user_{self.borrower.id}", called_groups)
        self.assertIn(f"loan_user_{self.lender.id}", called_groups)
