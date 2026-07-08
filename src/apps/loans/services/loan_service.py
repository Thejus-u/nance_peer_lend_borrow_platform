from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.audit.services import AuditEventService
from apps.loans.choices import LoanStatus
from apps.loans.events import publish_loan_event
from apps.loans.models import Loan


class LoanServiceError(Exception):
    """Base service exception for loan workflow operations."""


class InvalidLoanOperationError(LoanServiceError):
    """Raised when a state transition or input violates business rules."""


@dataclass(frozen=True)
class _IdempotencyRecord:
    loan_id: int
    fingerprint: str


class LoanService:
    IDEMPOTENCY_TTL_SECONDS = 60 * 60 * 24

    @classmethod
    @transaction.atomic
    def create_loan(
        cls,
        *,
        lender_id: int,
        borrower_id: int | None,
        borrower_mobile_number: str | None = None,
        principal_amount: Decimal,
        currency: str,
        interest_rate: Decimal,
        repayment_term_months: int,
        starts_at: date,
        ends_at: date,
        purpose: str = "",
        source_transaction_reference: str = "",
        idempotency_key: str,
    ) -> Loan:
        cls._ensure_positive_amount(principal_amount=principal_amount)

        borrower, status = cls._resolve_borrower(
            borrower_id=borrower_id,
            borrower_mobile_number=borrower_mobile_number,
        )
        cls._ensure_distinct_parties(borrower_id=borrower.id, lender_id=lender_id)

        fingerprint = cls._fingerprint(
            {
                "borrower_id": borrower.id,
                "borrower_mobile_number": borrower.mobile_number,
                "principal_amount": str(principal_amount),
                "currency": currency,
                "interest_rate": str(interest_rate),
                "repayment_term_months": repayment_term_months,
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
                "purpose": purpose,
                "source_transaction_reference": source_transaction_reference,
                "lender_id": lender_id,
            }
        )

        existing = cls._resolve_idempotent_result(
            action="create_loan",
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if existing is not None:
            return existing

        loan = Loan.objects.create(
            borrower=borrower,
            lender_id=lender_id,
            status=status,
            principal_amount=principal_amount,
            currency=currency,
            interest_rate=interest_rate,
            repayment_term_months=repayment_term_months,
            starts_at=starts_at,
            ends_at=ends_at,
            purpose=purpose,
            source_transaction_reference=source_transaction_reference,
            submitted_at=timezone.now(),
        )

        cls._store_idempotent_result(
            action="create_loan",
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            loan_id=loan.id,
        )
        cls._record_status_change(
            loan=loan,
            from_status=None,
            to_status=loan.status,
            actor_user_id=lender_id,
            action="loan.create",
        )
        if borrower.is_active:
            cls._queue_notification_on_commit(
                user_id=borrower.id,
                title="New Loan Request",
                message="You have received a new loan request.",
                notification_type="loan_created",
                dedupe_key=f"loan-created:{loan.id}",
                payload={"loan_id": loan.id, "status": loan.status},
            )
        cls._emit_event_on_commit(loan=loan, event="loan.created", actor_user_id=lender_id)
        return loan

    @classmethod
    @transaction.atomic
    def accept_loan(
        cls,
        *,
        loan_id: int,
        borrower_id: int,
        idempotency_key: str,
    ) -> Loan:
        fingerprint = cls._fingerprint({"loan_id": loan_id, "borrower_id": borrower_id})
        existing = cls._resolve_idempotent_result(
            action="accept_loan",
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if existing is not None:
            return existing

        loan = Loan.objects.select_for_update().get(id=loan_id)

        if borrower_id != loan.borrower_id:
            raise InvalidLoanOperationError("Only the borrower can accept this loan request.")

        if loan.status == LoanStatus.ACTIVE and loan.borrower_id == borrower_id:
            cls._store_idempotent_result(
                action="accept_loan",
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                loan_id=loan.id,
            )
            return loan

        if loan.status not in {LoanStatus.PENDING_REVIEW, LoanStatus.PENDING_INVITE}:
            raise InvalidLoanOperationError("Only pending loans can be accepted.")

        previous_status = loan.status
        loan.status = LoanStatus.ACTIVE
        loan.approved_at = timezone.now()
        loan.rejection_reason = ""
        loan.save(update_fields=["status", "approved_at", "rejection_reason", "updated_at"])
        cls._record_status_change(
            loan=loan,
            from_status=previous_status,
            to_status=loan.status,
            actor_user_id=borrower_id,
            action="loan.accept",
        )

        cls._store_idempotent_result(
            action="accept_loan",
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            loan_id=loan.id,
        )
        cls._queue_notification_on_commit(
            user_id=loan.lender_id,
            title="Loan Accepted",
            message="Your loan request has been accepted by the borrower.",
            notification_type="loan_accepted",
            dedupe_key=f"loan-accepted:{loan.id}",
            payload={"loan_id": loan.id, "status": loan.status},
        )
        cls._emit_event_on_commit(loan=loan, event="loan.accepted", actor_user_id=borrower_id)
        return loan

    @classmethod
    @transaction.atomic
    def reject_loan(
        cls,
        *,
        loan_id: int,
        borrower_id: int,
        reason: str,
        idempotency_key: str,
    ) -> Loan:
        fingerprint = cls._fingerprint({"loan_id": loan_id, "borrower_id": borrower_id, "reason": reason})
        existing = cls._resolve_idempotent_result(
            action="reject_loan",
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if existing is not None:
            return existing

        loan = Loan.objects.select_for_update().get(id=loan_id)

        if borrower_id != loan.borrower_id:
            raise InvalidLoanOperationError("Only the borrower can reject this loan request.")

        if loan.status == LoanStatus.REJECTED and loan.rejection_reason == reason:
            cls._store_idempotent_result(
                action="reject_loan",
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                loan_id=loan.id,
            )
            return loan

        if loan.status not in {LoanStatus.PENDING_REVIEW, LoanStatus.PENDING_INVITE}:
            raise InvalidLoanOperationError("Only pending loans can be rejected.")

        previous_status = loan.status
        loan.status = LoanStatus.REJECTED
        loan.rejection_reason = reason.strip()
        loan.save(update_fields=["status", "rejection_reason", "updated_at"])
        cls._record_status_change(
            loan=loan,
            from_status=previous_status,
            to_status=loan.status,
            actor_user_id=borrower_id,
            action="loan.reject",
            metadata={"reason": loan.rejection_reason},
        )

        cls._store_idempotent_result(
            action="reject_loan",
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            loan_id=loan.id,
        )
        cls._queue_notification_on_commit(
            user_id=loan.lender_id,
            title="Loan Rejected",
            message="Your loan request has been rejected by the borrower.",
            notification_type="loan_rejected",
            dedupe_key=f"loan-rejected:{loan.id}",
            payload={"loan_id": loan.id, "status": loan.status, "reason": loan.rejection_reason},
        )
        cls._emit_event_on_commit(loan=loan, event="loan.rejected", actor_user_id=borrower_id)
        return loan

    @classmethod
    @transaction.atomic
    def cancel_loan(
        cls,
        *,
        loan_id: int,
        requested_by_user_id: int,
        idempotency_key: str,
    ) -> Loan:
        fingerprint = cls._fingerprint(
            {"loan_id": loan_id, "requested_by_user_id": requested_by_user_id}
        )
        existing = cls._resolve_idempotent_result(
            action="cancel_loan",
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if existing is not None:
            return existing

        loan = Loan.objects.select_for_update().get(id=loan_id)

        if requested_by_user_id != loan.lender_id:
            raise InvalidLoanOperationError("Only the lender can cancel this loan request.")

        if loan.status == LoanStatus.CANCELLED:
            cls._store_idempotent_result(
                action="cancel_loan",
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                loan_id=loan.id,
            )
            return loan

        cancellable_statuses = {LoanStatus.PENDING_REVIEW}
        if loan.status not in cancellable_statuses:
            raise InvalidLoanOperationError("Loan can be cancelled only before borrower acceptance.")

        previous_status = loan.status
        loan.status = LoanStatus.CANCELLED
        loan.save(update_fields=["status", "updated_at"])
        cls._record_status_change(
            loan=loan,
            from_status=previous_status,
            to_status=loan.status,
            actor_user_id=requested_by_user_id,
            action="loan.cancel",
        )

        cls._store_idempotent_result(
            action="cancel_loan",
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            loan_id=loan.id,
        )
        cls._queue_notification_on_commit(
            user_id=loan.borrower_id,
            title="Loan Cancelled",
            message="The lender has cancelled this loan request.",
            notification_type="loan_cancelled",
            dedupe_key=f"loan-cancelled:{loan.id}",
            payload={"loan_id": loan.id, "status": loan.status},
        )
        cls._emit_event_on_commit(
            loan=loan,
            event="loan.cancelled",
            actor_user_id=requested_by_user_id,
        )
        return loan

    @staticmethod
    def _queue_notification_on_commit(
        *,
        user_id: int | None,
        title: str,
        message: str,
        notification_type: str,
        dedupe_key: str,
        payload: dict[str, object],
    ) -> None:
        if not user_id:
            return
        from apps.notifications.tasks import queue_notification_task

        queue_notification_task.delay(
            user_id=user_id,
            channel="in_app",
            title=title,
            message=message,
            notification_type=notification_type,
            dedupe_key=dedupe_key,
            payload=payload,
        )

    @staticmethod
    def _emit_event_on_commit(*, loan: Loan, event: str, actor_user_id: int | None) -> None:
        transaction.on_commit(
            lambda: publish_loan_event(loan=loan, event=event, actor_user_id=actor_user_id)
        )

    @staticmethod
    def _record_status_change(
        *,
        loan: Loan,
        from_status: str | None,
        to_status: str,
        actor_user_id: int | None,
        action: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        if from_status == to_status:
            return

        payload = {"action": action}
        if metadata:
            payload.update(metadata)

        AuditEventService.record_state_change(
            entity_type="loan",
            entity_id=loan.id,
            field_name="status",
            from_state=from_status,
            to_state=to_status,
            actor_user_id=actor_user_id,
            metadata=payload,
        )

    @staticmethod
    def _ensure_positive_amount(*, principal_amount: Decimal) -> None:
        if principal_amount <= Decimal("0"):
            raise InvalidLoanOperationError("Loan amount must be greater than 0.")

    @staticmethod
    def _ensure_distinct_parties(*, borrower_id: int | None, lender_id: int | None) -> None:
        if borrower_id is not None and lender_id is not None and borrower_id == lender_id:
            raise InvalidLoanOperationError("Borrower and lender must be different users.")

    @staticmethod
    def _resolve_borrower(*, borrower_id: int | None, borrower_mobile_number: str | None):
        user_model = get_user_model()

        if borrower_id is not None:
            borrower = user_model.objects.get(id=borrower_id)
            return borrower, LoanStatus.PENDING_REVIEW if borrower.is_active else LoanStatus.PENDING_INVITE

        normalized_mobile_number = (borrower_mobile_number or "").strip()
        if not normalized_mobile_number:
            raise InvalidLoanOperationError("Borrower mobile number is required.")

        borrower = user_model.objects.filter(mobile_number=normalized_mobile_number).first()
        if borrower is None:
            borrower = user_model.objects.create_user(
                mobile_number=normalized_mobile_number,
                password=None,
                name="Pending Invite",
                is_active=False,
            )
            return borrower, LoanStatus.PENDING_INVITE

        return borrower, LoanStatus.PENDING_REVIEW if borrower.is_active else LoanStatus.PENDING_INVITE

    @staticmethod
    def _cache_key(*, action: str, idempotency_key: str) -> str:
        if not idempotency_key or not idempotency_key.strip():
            raise InvalidLoanOperationError("Idempotency-Key is required.")
        return f"loan-service:{action}:{idempotency_key.strip()}"

    @staticmethod
    def _fingerprint(payload: dict[str, object]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def _resolve_idempotent_result(
        cls,
        *,
        action: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> Loan | None:
        key = cls._cache_key(action=action, idempotency_key=idempotency_key)
        cached = cache.get(key)
        if not cached:
            return None

        record = _IdempotencyRecord(**cached)
        if record.fingerprint != fingerprint:
            raise InvalidLoanOperationError(
                "Idempotency-Key was already used with different request data."
            )

        return Loan.objects.get(id=record.loan_id)

    @classmethod
    def _store_idempotent_result(
        cls,
        *,
        action: str,
        idempotency_key: str,
        fingerprint: str,
        loan_id: int,
    ) -> None:
        key = cls._cache_key(action=action, idempotency_key=idempotency_key)
        cache.set(
            key,
            {"loan_id": loan_id, "fingerprint": fingerprint},
            timeout=cls.IDEMPOTENCY_TTL_SECONDS,
        )
