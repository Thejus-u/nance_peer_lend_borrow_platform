from __future__ import annotations

from celery import shared_task

from apps.loans.services.repayment_service import RepaymentService


@shared_task(name="loans.send_overdue_reminders")
def send_overdue_reminders_task() -> int:
    return RepaymentService.send_overdue_reminders()