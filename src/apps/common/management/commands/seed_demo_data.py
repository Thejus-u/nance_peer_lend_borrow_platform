from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import GmailAccount, User
from apps.loans.choices import LoanStatus
from apps.loans.models import Loan, Repayment, RepaymentStatus
from apps.loans.services.loan_service import LoanService
from apps.loans.services.repayment_service import RepaymentService


class Command(BaseCommand):
    help = "Seed demo data with users, loans, and Gmail accounts for walkthroughs."

    @transaction.atomic
    def handle(self, *args, **options):
        user_specs = [
            ("+14150000001", "Asha Lender", "asha.demo@gmail.com"),
            ("+14150000002", "Bharat Borrower", "bharat.demo@gmail.com"),
            ("+14150000003", "Charu Family", "charu.demo@gmail.com"),
        ]

        users: dict[str, User] = {}
        for mobile, name, gmail in user_specs:
            user, _ = User.objects.update_or_create(
                mobile_number=mobile,
                defaults={"name": name, "is_active": True},
            )
            if not user.has_usable_password():
                user.set_password("StrongPass123!")
                user.save(update_fields=["password", "updated_at"])
            users[mobile] = user

            GmailAccount.objects.get_or_create(
                user=user,
                gmail_address=gmail,
                defaults={
                    "is_primary": True,
                    "is_verified": True,
                    "access_token": "demo-access-token",
                    "refresh_token": "demo-refresh-token",
                },
            )

        lender = users["+14150000001"]
        borrower = users["+14150000002"]
        family = users["+14150000003"]

        today = timezone.localdate()

        pending_review = self._get_or_create_loan(
            key="demo-pending-review",
            lender=lender,
            borrower=borrower,
            status=LoanStatus.PENDING_REVIEW,
            principal=Decimal("5000.00"),
            starts_at=today,
            ends_at=today + timedelta(days=60),
        )

        active = self._get_or_create_loan(
            key="demo-active",
            lender=lender,
            borrower=borrower,
            status=LoanStatus.ACTIVE,
            principal=Decimal("15000.00"),
            starts_at=today,
            ends_at=today + timedelta(days=120),
        )

        rejected = self._get_or_create_loan(
            key="demo-rejected",
            lender=lender,
            borrower=borrower,
            status=LoanStatus.REJECTED,
            principal=Decimal("8000.00"),
            starts_at=today,
            ends_at=today + timedelta(days=90),
            rejection_reason="Borrower cannot commit now.",
        )

        cancelled = self._get_or_create_loan(
            key="demo-cancelled",
            lender=lender,
            borrower=family,
            status=LoanStatus.CANCELLED,
            principal=Decimal("2200.00"),
            starts_at=today,
            ends_at=today + timedelta(days=45),
        )

        pending_invite = self._get_or_create_pending_invite_loan(
            lender=lender,
            borrower_mobile="+14150000099",
            principal=Decimal("3000.00"),
            starts_at=today,
            ends_at=today + timedelta(days=30),
        )

        closed = self._ensure_closed_loan(
            lender=lender,
            borrower=borrower,
            starts_at=today,
            ends_at=today + timedelta(days=30),
        )

        self.stdout.write(self.style.SUCCESS("Seed data ready."))
        self.stdout.write(f"Users: {User.objects.filter(mobile_number__in=[m for m, _, _ in user_specs]).count()}")
        self.stdout.write(
            "Loans: "
            f"pending_review={pending_review.id}, active={active.id}, rejected={rejected.id}, "
            f"cancelled={cancelled.id}, pending_invite={pending_invite.id}, closed={closed.id}"
        )

    def _get_or_create_loan(
        self,
        *,
        key: str,
        lender: User,
        borrower: User,
        status: str,
        principal: Decimal,
        starts_at,
        ends_at,
        rejection_reason: str = "",
    ) -> Loan:
        loan, _ = Loan.objects.get_or_create(
            purpose=key,
            lender=lender,
            borrower=borrower,
            defaults={
                "status": status,
                "principal_amount": principal,
                "currency": "INR",
                "interest_rate": Decimal("0.00"),
                "repayment_term_months": 1,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "submitted_at": timezone.now(),
                "rejection_reason": rejection_reason,
            },
        )
        if loan.status != status:
            loan.status = status
            loan.rejection_reason = rejection_reason
            loan.save(update_fields=["status", "rejection_reason", "updated_at"])
        return loan

    def _get_or_create_pending_invite_loan(
        self,
        *,
        lender: User,
        borrower_mobile: str,
        principal: Decimal,
        starts_at,
        ends_at,
    ) -> Loan:
        existing = Loan.objects.filter(
            lender=lender,
            borrower__mobile_number=borrower_mobile,
            status=LoanStatus.PENDING_INVITE,
            purpose="demo-pending-invite",
        ).first()
        if existing:
            return existing

        return LoanService.create_loan(
            lender_id=lender.id,
            borrower_id=None,
            borrower_mobile_number=borrower_mobile,
            principal_amount=principal,
            currency="INR",
            interest_rate=Decimal("0.00"),
            repayment_term_months=1,
            starts_at=starts_at,
            ends_at=ends_at,
            purpose="demo-pending-invite",
            idempotency_key="seed-demo-pending-invite",
        )

    def _ensure_closed_loan(self, *, lender: User, borrower: User, starts_at, ends_at) -> Loan:
        loan, _ = Loan.objects.get_or_create(
            purpose="demo-closed",
            lender=lender,
            borrower=borrower,
            defaults={
                "status": LoanStatus.ACTIVE,
                "principal_amount": Decimal("1200.00"),
                "currency": "INR",
                "interest_rate": Decimal("0.00"),
                "repayment_term_months": 1,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "submitted_at": timezone.now(),
                "approved_at": timezone.now(),
            },
        )

        if loan.status != LoanStatus.CLOSED:
            repayment = Repayment.objects.filter(loan=loan, installment_number=1).first()
            if not repayment:
                repayment = RepaymentService.create_repayment(
                    loan_id=loan.id,
                    installment_number=1,
                    due_date=timezone.localdate(),
                    amount_due=Decimal("1200.00"),
                )
            if repayment.status != RepaymentStatus.PAID:
                RepaymentService.apply_payment(
                    repayment_id=repayment.id,
                    payment_amount=repayment.amount_due - repayment.amount_paid,
                    transaction_reference="SEED-CLOSE-001",
                    note="Seed closure payment",
                )
            loan.refresh_from_db()

        return loan
