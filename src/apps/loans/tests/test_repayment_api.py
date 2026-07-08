from __future__ import annotations

from datetime import date, timedelta

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.loans.choices import LoanStatus
from apps.loans.models import Loan, Repayment, RepaymentStatus
from apps.notifications.models import Notification
from apps.payments.models import BankTransaction, DiscoveredAccount, DiscoveredAccountStatus


class RepaymentAPITestCase(APITestCase):
    def setUp(self) -> None:
        self.borrower = User.objects.create_user(
            mobile_number="+14157770001",
            name="Borrower Repay",
            password="StrongPass123!",
        )
        self.lender = User.objects.create_user(
            mobile_number="+14157770002",
            name="Lender Repay",
            password="StrongPass123!",
        )

        borrower_login = self.client.post(
            reverse("accounts:login"),
            {"mobile_number": self.borrower.mobile_number, "password": "StrongPass123!"},
            format="json",
        )
        self.borrower_access = borrower_login.data["access"]

        lender_login = self.client.post(
            reverse("accounts:login"),
            {"mobile_number": self.lender.mobile_number, "password": "StrongPass123!"},
            format="json",
        )
        self.lender_access = lender_login.data["access"]

        self.loan = Loan.objects.create(
            borrower=self.borrower,
            lender=self.lender,
            status=LoanStatus.APPROVED,
            principal_amount="1200.00",
            currency="USD",
            interest_rate="10.00",
            repayment_term_months=12,
            starts_at=date.today(),
            ends_at=date.today() + timedelta(days=365),
            purpose="Repayment API test",
        )

    def test_create_repayment_success(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")

        response = self.client.post(
            reverse("loans:repayment_create", kwargs={"loan_id": self.loan.id}),
            {
                "installment_number": 1,
                "due_date": (date.today() + timedelta(days=30)).isoformat(),
                "amount_due": "300.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["loan"], self.loan.id)
        self.assertEqual(response.data["status"], RepaymentStatus.SCHEDULED)
        self.assertTrue(
            Notification.objects.filter(
                user_id=self.borrower.id,
                notification_type="repayment_created",
            ).exists()
        )

    def test_create_repayment_is_idempotent_for_identical_duplicate_submission(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")
        payload = {
            "installment_number": 1,
            "due_date": (date.today() + timedelta(days=30)).isoformat(),
            "amount_due": "300.00",
        }

        first = self.client.post(
            reverse("loans:repayment_create", kwargs={"loan_id": self.loan.id}),
            payload,
            format="json",
        )
        second = self.client.post(
            reverse("loans:repayment_create", kwargs={"loan_id": self.loan.id}),
            payload,
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Repayment.objects.filter(loan=self.loan, installment_number=1).count(), 1)

    def test_create_repayment_rejects_conflicting_duplicate_installment(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")

        first = self.client.post(
            reverse("loans:repayment_create", kwargs={"loan_id": self.loan.id}),
            {
                "installment_number": 1,
                "due_date": (date.today() + timedelta(days=30)).isoformat(),
                "amount_due": "300.00",
            },
            format="json",
        )
        second = self.client.post(
            reverse("loans:repayment_create", kwargs={"loan_id": self.loan.id}),
            {
                "installment_number": 1,
                "due_date": (date.today() + timedelta(days=45)).isoformat(),
                "amount_due": "350.00",
            },
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Installment already exists", second.data["detail"])

    def test_pay_repayment_partial(self) -> None:
        repayment = Repayment.objects.create(
            loan=self.loan,
            installment_number=1,
            due_date=date.today() + timedelta(days=30),
            amount_due="300.00",
            amount_paid="0.00",
            status=RepaymentStatus.SCHEDULED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.borrower_access}")
        response = self.client.post(
            reverse("loans:repayment_pay", kwargs={"repayment_id": repayment.id}),
            {"payment_amount": "100.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], RepaymentStatus.PARTIAL)
        self.assertEqual(response.data["amount_paid"], "100.00")

    def test_pay_repayment_prevents_overpayment(self) -> None:
        repayment = Repayment.objects.create(
            loan=self.loan,
            installment_number=1,
            due_date=date.today() + timedelta(days=30),
            amount_due="200.00",
            amount_paid="0.00",
            status=RepaymentStatus.SCHEDULED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.borrower_access}")
        response = self.client.post(
            reverse("loans:repayment_pay", kwargs={"repayment_id": repayment.id}),
            {"payment_amount": "250.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_pay_repayment_auto_settles_loan(self) -> None:
        repayment = Repayment.objects.create(
            loan=self.loan,
            installment_number=1,
            due_date=date.today() + timedelta(days=30),
            amount_due="400.00",
            amount_paid="0.00",
            status=RepaymentStatus.SCHEDULED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.borrower_access}")
        response = self.client.post(
            reverse("loans:repayment_pay", kwargs={"repayment_id": repayment.id}),
            {"payment_amount": "400.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], RepaymentStatus.PAID)

        self.loan.refresh_from_db()
        self.assertEqual(self.loan.status, LoanStatus.CLOSED)
        self.assertIsNotNone(self.loan.closed_at)
        self.assertTrue(
            Notification.objects.filter(
                user_id=self.lender.id,
                notification_type="repayment_completed",
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user_id=self.lender.id,
                notification_type="loan_settled",
            ).exists()
        )

    def test_repayment_create_requires_authentication(self) -> None:
        response = self.client.post(
            reverse("loans:repayment_create", kwargs={"loan_id": self.loan.id}),
            {
                "installment_number": 1,
                "due_date": (date.today() + timedelta(days=30)).isoformat(),
                "amount_due": "300.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pay_repayment_matches_bank_transaction_by_reference(self) -> None:
        repayment = Repayment.objects.create(
            loan=self.loan,
            installment_number=2,
            due_date=date.today() + timedelta(days=30),
            amount_due="250.00",
            amount_paid="0.00",
            status=RepaymentStatus.SCHEDULED,
        )
        bank_transaction = BankTransaction.objects.create(
            user=self.borrower,
            amount="250.00",
            transaction_date=self.loan.starts_at,
            narration="UPI repayment REF-250",
            direction="debit",
            account_number="1234567890",
            bank="ACME BANK",
            account_type="savings",
        )
        DiscoveredAccount.objects.create(
            user=self.borrower,
            account_number="1234567890",
            bank="ACME BANK",
            account_type="savings",
            status=DiscoveredAccountStatus.LINKED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.borrower_access}")
        response = self.client.post(
            reverse("loans:repayment_pay", kwargs={"repayment_id": repayment.id}),
            {"payment_amount": "250.00", "transaction_reference": "REF-250", "note": "UPI repayment"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["matched_transaction"], bank_transaction.id)
        self.assertEqual(response.data["match_confidence"], "high")
        self.assertFalse(response.data["requires_manual_review"])

    def test_pay_repayment_flags_unmatched_reference_for_manual_review(self) -> None:
        repayment = Repayment.objects.create(
            loan=self.loan,
            installment_number=3,
            due_date=date.today() + timedelta(days=30),
            amount_due="260.00",
            amount_paid="0.00",
            status=RepaymentStatus.SCHEDULED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.borrower_access}")
        response = self.client.post(
            reverse("loans:repayment_pay", kwargs={"repayment_id": repayment.id}),
            {"payment_amount": "50.00", "transaction_reference": "UNKNOWN-REF"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["matched_transaction"])
        self.assertEqual(response.data["match_confidence"], "")
        self.assertTrue(response.data["requires_manual_review"])
