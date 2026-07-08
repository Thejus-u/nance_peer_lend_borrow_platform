from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.loans.choices import LoanStatus
from apps.loans.validators import validate_non_negative_amount, validate_positive_amount


class Loan(models.Model):
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False, db_index=True)

    borrower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="borrowed_loans",
    )
    lender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="funded_loans",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=32,
        choices=LoanStatus.choices,
        default=LoanStatus.DRAFT,
        db_index=True,
    )

    principal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, default="USD")
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )
    repayment_term_months = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(360)]
    )

    starts_at = models.DateField()
    ends_at = models.DateField()

    purpose = models.TextField(blank=True)
    source_transaction_reference = models.CharField(max_length=255, blank=True, db_index=True)
    rejection_reason = models.TextField(blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="loan_status_idx"),
            models.Index(fields=["borrower", "status"], name="loan_borrower_status_idx"),
            models.Index(fields=["lender", "status"], name="loan_lender_status_idx"),
            models.Index(fields=["created_at"], name="loan_created_at_idx"),
            models.Index(fields=["starts_at", "ends_at"], name="loan_period_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(principal_amount__gt=0),
                name="loan_principal_amount_gt_zero",
            ),
            models.CheckConstraint(
                check=Q(interest_rate__gte=0) & Q(interest_rate__lte=100),
                name="loan_interest_rate_between_0_100",
            ),
            models.CheckConstraint(
                check=Q(repayment_term_months__gte=1),
                name="loan_repayment_term_months_gte_1",
            ),
            models.CheckConstraint(
                check=Q(ends_at__gt=F("starts_at")),
                name="loan_ends_at_after_starts_at",
            ),
            models.CheckConstraint(
                check=Q(lender__isnull=True) | ~Q(borrower=F("lender")),
                name="loan_lender_not_borrower",
            ),
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}

        if self.currency and self.currency != self.currency.upper():
            errors["currency"] = "Currency must be uppercase ISO code, for example USD."

        if self.lender_id and self.borrower_id == self.lender_id:
            errors["lender"] = "Lender cannot be the same as borrower."

        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "Loan end date must be later than start date."

        if self.approved_at and self.submitted_at and self.approved_at < self.submitted_at:
            errors["approved_at"] = "Approved time cannot be earlier than submitted time."

        if self.disbursed_at and self.approved_at and self.disbursed_at < self.approved_at:
            errors["disbursed_at"] = "Disbursed time cannot be earlier than approved time."

        if self.closed_at and self.disbursed_at and self.closed_at < self.disbursed_at:
            errors["closed_at"] = "Closed time cannot be earlier than disbursed time."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.public_id} - {self.get_status_display()}"


class RepaymentStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    PARTIAL = "partial", "Partially Paid"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"


class RepaymentMatchConfidence(models.TextChoices):
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class Repayment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="repayments")
    installment_number = models.PositiveIntegerField()

    due_date = models.DateField(db_index=True)
    amount_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[validate_positive_amount],
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative_amount],
    )
    note = models.TextField(blank=True)
    transaction_reference = models.CharField(max_length=255, blank=True, db_index=True)
    matched_transaction = models.ForeignKey(
        "payments.BankTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matched_repayments",
    )
    match_confidence = models.CharField(
        max_length=10,
        choices=RepaymentMatchConfidence.choices,
        blank=True,
    )
    requires_manual_review = models.BooleanField(default=False, db_index=True)

    status = models.CharField(
        max_length=20,
        choices=RepaymentStatus.choices,
        default=RepaymentStatus.SCHEDULED,
        db_index=True,
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["loan_id", "installment_number"]
        indexes = [
            models.Index(fields=["loan", "status"], name="repayment_loan_status_idx"),
            models.Index(fields=["loan", "due_date"], name="repayment_loan_due_date_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "installment_number"],
                name="repayment_unique_installment_per_loan",
            ),
            models.CheckConstraint(
                check=Q(amount_due__gt=0),
                name="repayment_amount_due_gt_zero",
            ),
            models.CheckConstraint(
                check=Q(amount_paid__gte=0),
                name="repayment_amount_paid_non_negative",
            ),
            models.CheckConstraint(
                check=Q(amount_paid__lte=F("amount_due")),
                name="repayment_amount_paid_lte_amount_due",
            ),
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}

        if self.amount_paid > self.amount_due:
            errors["amount_paid"] = "Amount paid cannot be greater than amount due."

        if self.status == RepaymentStatus.PAID and self.amount_paid != self.amount_due:
            errors["status"] = "Paid repayment must have amount_paid equal to amount_due."

        if self.status == RepaymentStatus.PAID and not self.paid_at:
            errors["paid_at"] = "paid_at is required when repayment is paid."

        if self.status in {RepaymentStatus.SCHEDULED, RepaymentStatus.OVERDUE} and self.amount_paid > 0:
            errors["status"] = "Scheduled or overdue repayment cannot contain a positive paid amount."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Loan {self.loan_id} installment {self.installment_number} ({self.status})"
