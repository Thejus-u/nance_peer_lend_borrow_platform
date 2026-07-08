from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.loans.models import Loan
from apps.loans.services.loan_service import LoanService
from apps.loans.services.repayment_service import RepaymentService
from apps.notifications.models import NotificationChannel
from apps.notifications.services.notification_service import NotificationService
from apps.payments.models import DiscoveredAccountStatus
from apps.payments.services.discovered_account_service import DiscoveredAccountService


class StateChangeAuditingTestCase(TestCase):
    def setUp(self) -> None:
        self.borrower = User.objects.create_user(
            mobile_number="+14156660003",
            name="Borrower Audit",
            password="StrongPass123!",
        )
        self.lender = User.objects.create_user(
            mobile_number="+14156660004",
            name="Lender Audit",
            password="StrongPass123!",
        )

    def test_loan_status_change_creates_audit_record(self) -> None:
        loan = LoanService.create_loan(
            lender_id=self.lender.id,
            borrower_id=self.borrower.id,
            principal_amount=Decimal("1000.00"),
            currency="USD",
            interest_rate=Decimal("8.00"),
            repayment_term_months=12,
            starts_at=date.today(),
            ends_at=date.today() + timedelta(days=365),
            idempotency_key="audit-loan-create-key",
        )

        LoanService.accept_loan(
            loan_id=loan.id,
            borrower_id=self.borrower.id,
            idempotency_key="audit-loan-accept-key",
        )

        self.assertTrue(
            AuditEvent.objects.filter(
                entity_type="loan",
                entity_id=str(loan.id),
                field_name="status",
                from_state="pending_review",
                to_state="active",
            ).exists()
        )

    def test_repayment_status_change_creates_audit_record(self) -> None:
        loan = Loan.objects.create(
            borrower=self.borrower,
            lender=self.lender,
            status="approved",
            principal_amount="1200.00",
            currency="USD",
            interest_rate="9.00",
            repayment_term_months=12,
            starts_at=date.today(),
            ends_at=date.today() + timedelta(days=365),
            purpose="Repayment audit",
        )

        repayment = RepaymentService.create_repayment(
            loan_id=loan.id,
            installment_number=1,
            due_date=date.today() + timedelta(days=30),
            amount_due=Decimal("300.00"),
        )

        RepaymentService.apply_payment(repayment_id=repayment.id, payment_amount=Decimal("100.00"))

        self.assertTrue(
            AuditEvent.objects.filter(
                entity_type="repayment",
                entity_id=str(repayment.id),
                field_name="status",
                from_state="scheduled",
                to_state="partial",
            ).exists()
        )

    def test_discovered_account_status_change_creates_audit_record(self) -> None:
        account = DiscoveredAccountService.discover_account(
            user_id=self.borrower.id,
            account_number="9876543210",
            bank="Audit Bank",
            account_type="savings",
        )

        DiscoveredAccountService.link_account(account_id=account.id, user_id=self.borrower.id)

        self.assertTrue(
            AuditEvent.objects.filter(
                entity_type="discovered_account",
                entity_id=str(account.id),
                field_name="status",
                from_state=DiscoveredAccountStatus.UNLINKED,
                to_state=DiscoveredAccountStatus.LINKED,
            ).exists()
        )

    def test_notification_status_change_creates_audit_record(self) -> None:
        notification = NotificationService.create_notification(
            user_id=self.borrower.id,
            channel=NotificationChannel.IN_APP,
            title="Audit",
            message="Notification audit",
        )

        NotificationService.mark_sent(notification_id=notification.id)

        self.assertTrue(
            AuditEvent.objects.filter(
                entity_type="notification",
                entity_id=str(notification.id),
                field_name="status",
                from_state="pending",
                to_state="sent",
            ).exists()
        )
