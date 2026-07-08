from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.loans.choices import LoanStatus
from apps.loans.models import Loan, Repayment, RepaymentStatus
from apps.notifications.models import Notification


class LoanAPITestCase(APITestCase):
    def setUp(self) -> None:
        self.borrower = User.objects.create_user(
            mobile_number="+14150000001",
            name="Borrower One",
            password="StrongPass123!",
        )
        self.lender = User.objects.create_user(
            mobile_number="+14150000002",
            name="Lender One",
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

    def _loan_payload(self, idempotency_key: str) -> dict[str, object]:
        return {
            "borrower_mobile_number": self.borrower.mobile_number,
            "principal_amount": "1000.00",
            "currency": "usd",
            "interest_rate": "8.50",
            "repayment_term_months": 12,
            "starts_at": date.today().isoformat(),
            "ends_at": (date.today() + timedelta(days=365)).isoformat(),
            "purpose": "Home renovation",
            "idempotency_key": idempotency_key,
        }

    def _create_pending_loan(self, idempotency_key: str = "loan-create-key") -> Loan:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")
        response = self.client.post(reverse("loans:create"), self._loan_payload(idempotency_key), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return Loan.objects.get(id=response.data["id"])

    def test_create_loan_success(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")

        response = self.client.post(
            reverse("loans:create"),
            self._loan_payload("loan-create-1"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], LoanStatus.PENDING_REVIEW)
        self.assertEqual(response.data["borrower"], self.borrower.id)
        self.assertEqual(response.data["lender"], self.lender.id)
        self.assertEqual(response.data["currency"], "USD")
        self.assertTrue(
            Notification.objects.filter(
                user_id=self.borrower.id,
                notification_type="loan_created",
            ).exists()
        )

    def test_create_loan_supports_source_transaction_reference(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")
        payload = self._loan_payload("loan-create-src-ref")
        payload["source_transaction_reference"] = "UPI-REF-123"

        response = self.client.post(reverse("loans:create"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["source_transaction_reference"], "UPI-REF-123")

    def test_create_loan_idempotent_repeat_returns_same_loan(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")
        payload = self._loan_payload("loan-create-idem")

        first = self.client.post(reverse("loans:create"), payload, format="json")
        second = self.client.post(reverse("loans:create"), payload, format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data["id"], second.data["id"])

    def test_create_loan_supports_idempotency_key_header(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")
        payload = self._loan_payload("loan-create-header")
        payload.pop("idempotency_key")

        first = self.client.post(
            reverse("loans:create"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="loan-create-header-idem",
        )
        second = self.client.post(
            reverse("loans:create"),
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="loan-create-header-idem",
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data["id"], second.data["id"])

    def test_accept_loan_success(self) -> None:
        loan = self._create_pending_loan("loan-create-accept")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.borrower_access}")
        response = self.client.post(
            reverse("loans:accept", kwargs={"loan_id": loan.id}),
            {"idempotency_key": "loan-accept-1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], LoanStatus.ACTIVE)
        self.assertEqual(response.data["lender"], self.lender.id)
        self.assertTrue(
            Notification.objects.filter(
                user_id=self.lender.id,
                notification_type="loan_accepted",
            ).exists()
        )

    def test_reject_loan_success(self) -> None:
        loan = self._create_pending_loan("loan-create-reject")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.borrower_access}")
        response = self.client.post(
            reverse("loans:reject", kwargs={"loan_id": loan.id}),
            {"reason": "Risk profile did not match", "idempotency_key": "loan-reject-1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], LoanStatus.REJECTED)
        self.assertEqual(response.data["rejection_reason"], "Risk profile did not match")
        self.assertTrue(
            Notification.objects.filter(
                user_id=self.lender.id,
                notification_type="loan_rejected",
            ).exists()
        )

    def test_cancel_loan_success_for_lender_before_acceptance(self) -> None:
        loan = self._create_pending_loan("loan-create-cancel")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")
        response = self.client.post(
            reverse("loans:cancel", kwargs={"loan_id": loan.id}),
            {"idempotency_key": "loan-cancel-1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], LoanStatus.CANCELLED)
        self.assertTrue(
            Notification.objects.filter(
                user_id=self.borrower.id,
                notification_type="loan_cancelled",
            ).exists()
        )

    def test_cancel_loan_fails_for_borrower(self) -> None:
        loan = self._create_pending_loan("loan-create-cancel-fail")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.borrower_access}")
        response = self.client.post(
            reverse("loans:cancel", kwargs={"loan_id": loan.id}),
            {"idempotency_key": "loan-cancel-2"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_detail_visible_to_participant(self) -> None:
        loan = self._create_pending_loan("loan-create-detail")
        Repayment.objects.create(
            loan=loan,
            installment_number=1,
            due_date=date.today() + timedelta(days=30),
            amount_due="100.00",
            amount_paid="0.00",
            status=RepaymentStatus.SCHEDULED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.borrower_access}")
        response = self.client.get(reverse("loans:detail", kwargs={"pk": loan.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], loan.id)
        self.assertEqual(len(response.data["repayment_history"]), 1)

    def test_create_requires_authentication(self) -> None:
        response = self.client.post(reverse("loans:create"), self._loan_payload("loan-auth-fail"), format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_accept_fails_when_lender_tries_to_accept(self) -> None:
        loan = self._create_pending_loan("loan-create-borrower-accept")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")
        response = self.client.post(
            reverse("loans:accept", kwargs={"loan_id": loan.id}),
            {"idempotency_key": "loan-accept-borrower"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_incoming_query_returns_pending_requests_for_borrower(self) -> None:
        loan = self._create_pending_loan("loan-create-incoming")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.borrower_access}")
        response = self.client.get(reverse("loans:incoming"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], loan.id)

    def test_lent_borrowed_active_settled_queries(self) -> None:
        loan = self._create_pending_loan("loan-create-query")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.borrower_access}")
        self.client.post(
            reverse("loans:accept", kwargs={"loan_id": loan.id}),
            {"idempotency_key": "loan-query-accept"},
            format="json",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")
        lent_response = self.client.get(reverse("loans:lent"))
        active_response = self.client.get(reverse("loans:active"))

        self.assertEqual(lent_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(lent_response.data["count"], 1)
        self.assertEqual(active_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(active_response.data["count"], 1)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.borrower_access}")
        borrowed_response = self.client.get(reverse("loans:borrowed"))
        settled_response = self.client.get(reverse("loans:settled"))

        self.assertEqual(borrowed_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(borrowed_response.data["count"], 1)
        self.assertEqual(settled_response.status_code, status.HTTP_200_OK)

    def test_amount_must_be_greater_than_zero(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")
        payload = self._loan_payload("loan-create-zero")
        payload["principal_amount"] = str(Decimal("0.00"))

        response = self.client.post(reverse("loans:create"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_loan_for_non_onboarded_mobile_creates_pending_invite(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.lender_access}")
        payload = self._loan_payload("loan-create-invite")
        payload["borrower_mobile_number"] = "+14150000099"

        response = self.client.post(reverse("loans:create"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], LoanStatus.PENDING_INVITE)
        invited_borrower = User.objects.get(mobile_number="+14150000099")
        self.assertFalse(invited_borrower.is_active)
