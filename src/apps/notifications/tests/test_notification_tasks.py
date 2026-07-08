from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.loans.choices import LoanStatus
from apps.loans.models import Loan, Repayment, RepaymentStatus
from apps.loans.tasks import send_overdue_reminders_task
from apps.notifications.models import Notification, NotificationChannel, NotificationStatus
from apps.notifications.tasks import dispatch_pending_notifications_task, queue_notification_task


class NotificationTasksTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            mobile_number="+14151110003",
            name="Task User",
            password="StrongPass123!",
        )

    def test_queue_notification_task_creates_notification(self) -> None:
        notification_id = queue_notification_task(
            user_id=self.user.id,
            channel=NotificationChannel.IN_APP,
            title="Queued",
            message="Queued message",
            payload={"event": "queued"},
        )

        notification = Notification.objects.get(id=notification_id)
        self.assertEqual(notification.user_id, self.user.id)
        self.assertEqual(notification.status, NotificationStatus.PENDING)

    def test_dispatch_pending_notifications_task_marks_notifications_sent(self) -> None:
        Notification.objects.create(
            user=self.user,
            channel=NotificationChannel.EMAIL,
            title="Dispatch",
            message="Dispatch me",
        )

        sent_count = dispatch_pending_notifications_task(limit=5)

        self.assertEqual(sent_count, 1)
        self.assertEqual(Notification.objects.get().status, NotificationStatus.SENT)

    def test_send_overdue_reminders_task_creates_overdue_notification(self) -> None:
        lender = User.objects.create_user(
            mobile_number="+14151110004",
            name="Lender",
            password="StrongPass123!",
        )
        loan = Loan.objects.create(
            borrower=self.user,
            lender=lender,
            status=LoanStatus.ACTIVE,
            principal_amount="100.00",
            currency="USD",
            interest_rate="5.00",
            repayment_term_months=3,
            starts_at=timezone.localdate(),
	            ends_at=timezone.localdate() + timedelta(days=30),
            purpose="Overdue reminder",
        )
        repayment = Repayment.objects.create(
            loan=loan,
            installment_number=1,
	            due_date=timezone.localdate() - timedelta(days=2),
            amount_due="100.00",
            amount_paid="0.00",
            status=RepaymentStatus.SCHEDULED,
        )

        reminder_count = send_overdue_reminders_task()

        repayment.refresh_from_db()
        self.assertEqual(reminder_count, 1)
        self.assertEqual(repayment.status, RepaymentStatus.OVERDUE)
        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                notification_type="repayment_overdue",
            ).exists()
        )
