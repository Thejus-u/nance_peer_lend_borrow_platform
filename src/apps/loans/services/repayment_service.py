from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils import timezone

from apps.audit.services import AuditEventService
from apps.loans.choices import LoanStatus
from apps.loans.models import Loan, Repayment, RepaymentStatus


class RepaymentServiceError(Exception):
    """Base service exception for repayment operations."""


class InvalidRepaymentOperationError(RepaymentServiceError):
    """Raised when repayment operation violates business constraints."""


class RepaymentService:
    @classmethod
    @transaction.atomic
    def create_repayment(
        cls,
        *,
        loan_id: int,
        installment_number: int,
        due_date,
        amount_due: Decimal,
    ) -> Repayment:
        loan = Loan.objects.select_for_update().get(id=loan_id)

        if amount_due <= Decimal("0"):
            raise InvalidRepaymentOperationError("Repayment amount_due must be greater than 0.")

        if installment_number <= 0:
            raise InvalidRepaymentOperationError("Installment number must be greater than 0.")

        if loan.status in {LoanStatus.CANCELLED, LoanStatus.REJECTED, LoanStatus.CLOSED}:
            raise InvalidRepaymentOperationError(
                "Repayments cannot be created for cancelled, rejected, or closed loans."
            )

        existing = (
            Repayment.objects.select_for_update()
            .filter(loan_id=loan_id, installment_number=installment_number)
            .first()
        )
        if existing is not None:
            return cls._resolve_existing_installment(
                existing=existing,
                due_date=due_date,
                amount_due=amount_due,
            )

        try:
            repayment = Repayment.objects.create(
                loan=loan,
                installment_number=installment_number,
                due_date=due_date,
                amount_due=amount_due,
                amount_paid=Decimal("0.00"),
                status=RepaymentStatus.SCHEDULED,
            )
        except IntegrityError:
            existing_after_conflict = Repayment.objects.filter(
                loan_id=loan_id,
                installment_number=installment_number,
            ).first()
            if existing_after_conflict is not None:
                return cls._resolve_existing_installment(
                    existing=existing_after_conflict,
                    due_date=due_date,
                    amount_due=amount_due,
                )
            raise InvalidRepaymentOperationError("Unable to create repayment due to a concurrency conflict.")
        except ValidationError as exc:
            message = "; ".join(exc.messages) if exc.messages else "Invalid repayment request."
            raise InvalidRepaymentOperationError(message) from exc

        setattr(repayment, "_created", True)
        AuditEventService.record_state_change(
            entity_type="repayment",
            entity_id=repayment.id,
            field_name="status",
            from_state=None,
            to_state=repayment.status,
            actor_user_id=loan.lender_id,
            metadata={"action": "repayment.create", "loan_id": loan.id},
        )
        cls._queue_notification_on_commit(
            user_id=loan.borrower_id,
            title="Repayment Scheduled",
            message="A new repayment installment has been created for your loan.",
            notification_type="repayment_created",
            dedupe_key=f"repayment-created:{repayment.id}",
            payload={"loan_id": loan.id, "repayment_id": repayment.id, "status": repayment.status},
        )
        return repayment

    @staticmethod
    def _resolve_existing_installment(
        *,
        existing: Repayment,
        due_date,
        amount_due: Decimal,
    ) -> Repayment:
        if existing.due_date == due_date and existing.amount_due == amount_due:
            setattr(existing, "_created", False)
            return existing

        raise InvalidRepaymentOperationError(
            "Installment already exists for this loan with different due_date or amount_due."
        )

    @classmethod
    @transaction.atomic
    def apply_payment(
        cls,
        *,
        repayment_id: int,
        payment_amount: Decimal,
        paid_at: datetime | None = None,
        note: str = "",
        transaction_reference: str = "",
    ) -> Repayment:
        if payment_amount <= Decimal("0"):
            raise InvalidRepaymentOperationError("Payment amount must be greater than 0.")

        repayment = (
            Repayment.objects.select_for_update()
            .select_related("loan")
            .get(id=repayment_id)
        )
        loan = Loan.objects.select_for_update().get(id=repayment.loan_id)

        if loan.status in {LoanStatus.CANCELLED, LoanStatus.REJECTED}:
            raise InvalidRepaymentOperationError(
                "Payments cannot be recorded for cancelled or rejected loans."
            )

        if repayment.status == RepaymentStatus.PAID:
            raise InvalidRepaymentOperationError("Repayment is already fully paid.")

        remaining = repayment.amount_due - repayment.amount_paid
        if payment_amount > remaining:
            raise InvalidRepaymentOperationError(
                "Payment exceeds outstanding amount and would cause overpayment."
            )

        repayment.amount_paid += payment_amount

        previous_status = repayment.status
        effective_paid_at = paid_at or timezone.now()

        if repayment.amount_paid == repayment.amount_due:
            repayment.status = RepaymentStatus.PAID
            repayment.paid_at = effective_paid_at
        else:
            repayment.status = RepaymentStatus.PARTIAL
            repayment.paid_at = None

        repayment.note = note.strip()
        repayment.transaction_reference = transaction_reference.strip()

        from apps.payments.services.reconciliation_service import ReconciliationService

        reconciliation = ReconciliationService.match_repayment_transaction(
            user_id=loan.borrower_id,
            repayment=repayment,
            payment_amount=payment_amount,
            paid_at=effective_paid_at,
            transaction_reference=repayment.transaction_reference,
        )
        repayment.matched_transaction = reconciliation.matched_transaction
        repayment.match_confidence = reconciliation.match_confidence or ""
        repayment.requires_manual_review = reconciliation.requires_manual_review

        repayment.save(
            update_fields=[
                "amount_paid",
                "status",
                "paid_at",
                "note",
                "transaction_reference",
                "matched_transaction",
                "match_confidence",
                "requires_manual_review",
                "updated_at",
            ]
        )
        if previous_status != repayment.status:
            AuditEventService.record_state_change(
                entity_type="repayment",
                entity_id=repayment.id,
                field_name="status",
                from_state=previous_status,
                to_state=repayment.status,
                actor_user_id=loan.borrower_id,
                metadata={"action": "repayment.apply_payment", "loan_id": loan.id},
            )
            if repayment.status == RepaymentStatus.PAID:
                cls._queue_notification_on_commit(
                    user_id=loan.lender_id,
                    title="Repayment Completed",
                    message="A repayment installment has been fully paid.",
                    notification_type="repayment_completed",
                    dedupe_key=f"repayment-completed:{repayment.id}",
                    payload={"loan_id": loan.id, "repayment_id": repayment.id, "status": repayment.status},
                )

        cls._auto_settle_loan_if_fully_paid(loan=loan)

        return repayment

    @classmethod
    def _auto_settle_loan_if_fully_paid(cls, *, loan: Loan) -> None:
        has_outstanding = loan.repayments.exclude(status=RepaymentStatus.PAID).exists()
        if has_outstanding:
            return

        if loan.status != LoanStatus.CLOSED:
            previous_status = loan.status
            loan.status = LoanStatus.CLOSED
            loan.closed_at = timezone.now()
            loan.save(update_fields=["status", "closed_at", "updated_at"])
            AuditEventService.record_state_change(
                entity_type="loan",
                entity_id=loan.id,
                field_name="status",
                from_state=previous_status,
                to_state=loan.status,
                actor_user_id=loan.borrower_id,
                metadata={"action": "loan.auto_close_after_repayment"},
            )
            cls._queue_notification_on_commit(
                user_id=loan.lender_id,
                title="Loan Settled",
                message="Loan has been fully settled and closed.",
                notification_type="loan_settled",
                dedupe_key=f"loan-settled:{loan.id}",
                payload={"loan_id": loan.id, "status": loan.status},
            )

    @classmethod
    @transaction.atomic
    def send_overdue_reminders(cls) -> int:
        today = timezone.localdate()
        overdue_repayments = (
            Repayment.objects.select_for_update()
            .select_related("loan")
            .filter(due_date__lt=today)
            .exclude(status=RepaymentStatus.PAID)
        )

        reminder_count = 0
        for repayment in overdue_repayments:
            loan = repayment.loan
            if loan.status in {LoanStatus.CANCELLED, LoanStatus.REJECTED, LoanStatus.CLOSED}:
                continue

            if repayment.amount_paid == Decimal("0.00") and repayment.status == RepaymentStatus.SCHEDULED:
                previous_status = repayment.status
                repayment.status = RepaymentStatus.OVERDUE
                repayment.save(update_fields=["status", "updated_at"])
                AuditEventService.record_state_change(
                    entity_type="repayment",
                    entity_id=repayment.id,
                    field_name="status",
                    from_state=previous_status,
                    to_state=repayment.status,
                    actor_user_id=loan.borrower_id,
                    metadata={"action": "repayment.mark_overdue", "loan_id": loan.id},
                )

            cls._queue_notification_on_commit(
                user_id=loan.borrower_id,
                title="Repayment Overdue",
                message="A repayment installment is overdue.",
                notification_type="repayment_overdue",
                dedupe_key=f"repayment-overdue:{repayment.id}:{repayment.due_date.isoformat()}",
                payload={"loan_id": loan.id, "repayment_id": repayment.id, "status": repayment.status},
            )
            reminder_count += 1

        return reminder_count

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
