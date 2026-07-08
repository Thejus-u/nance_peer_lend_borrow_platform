from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class TransactionDirection(models.TextChoices):
    DEBIT = "debit", "Debit"
    CREDIT = "credit", "Credit"


class AccountType(models.TextChoices):
    SAVINGS = "savings", "Savings"
    CURRENT = "current", "Current"
    WALLET = "wallet", "Wallet"
    OTHER = "other", "Other"


class TransactionSource(models.TextChoices):
    MANUAL = "manual", "Manual"
    GMAIL = "gmail", "Gmail"


class DiscoveredAccountStatus(models.TextChoices):
    LINKED = "linked", "Linked"
    DISMISSED = "dismissed", "Dismissed"
    UNLINKED = "unlinked", "Unlinked"


class BankTransaction(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bank_transactions",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    transaction_date = models.DateTimeField()
    narration = models.TextField(blank=True)
    direction = models.CharField(
        max_length=10,
        choices=TransactionDirection.choices,
        db_index=True,
    )
    account_number = models.CharField(max_length=32, db_index=True)
    bank = models.CharField(max_length=120, db_index=True)
    account_type = models.CharField(max_length=20, choices=AccountType.choices, db_index=True)
    source = models.CharField(
        max_length=20,
        choices=TransactionSource.choices,
        default=TransactionSource.MANUAL,
        db_index=True,
    )
    raw_email_reference_id = models.CharField(max_length=255, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-transaction_date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "transaction_date"], name="bank_tx_user_date_idx"),
            models.Index(fields=["user", "direction"], name="bank_tx_user_direction_idx"),
            models.Index(fields=["bank", "account_number"], name="bank_tx_bank_account_idx"),
        ]
        constraints = [
            models.CheckConstraint(check=Q(amount__gt=0), name="bank_tx_amount_gt_zero"),
            models.CheckConstraint(
                check=Q(raw_email_reference_id="") | Q(source=TransactionSource.GMAIL),
                name="bank_tx_raw_ref_requires_gmail_source",
            ),
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}

        if self.account_number and len(self.account_number.strip()) < 4:
            errors["account_number"] = "Account number must contain at least 4 characters."

        if self.bank and len(self.bank.strip()) < 2:
            errors["bank"] = "Bank name must contain at least 2 characters."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user_id}:{self.direction}:{self.amount}:{self.transaction_date.isoformat()}"


class DiscoveredAccount(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="discovered_accounts",
    )
    account_number = models.CharField(max_length=32)
    bank = models.CharField(max_length=120)
    account_type = models.CharField(max_length=20, choices=AccountType.choices, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=DiscoveredAccountStatus.choices,
        default=DiscoveredAccountStatus.UNLINKED,
        db_index=True,
    )
    first_seen_at = models.DateTimeField(auto_now_add=True)
    supporting_email_count = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "account_number", "bank", "account_type"],
                name="discovered_account_unique_per_user",
            )
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="disc_acc_user_status_idx"),
            models.Index(fields=["bank", "account_number"], name="disc_acc_bank_acct_idx"),
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}

        if self.account_number and len(self.account_number.strip()) < 4:
            errors["account_number"] = "Account number must contain at least 4 characters."

        if self.bank and len(self.bank.strip()) < 2:
            errors["bank"] = "Bank name must contain at least 2 characters."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.account_number = self.account_number.strip()
        self.bank = self.bank.strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user_id}:{self.bank}:{self.account_number}:{self.status}"
