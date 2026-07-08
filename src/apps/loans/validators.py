from decimal import Decimal

from django.core.exceptions import ValidationError



def validate_positive_amount(value: Decimal) -> None:
    if value <= Decimal("0"):
        raise ValidationError("Amount must be greater than 0.")



def validate_non_negative_amount(value: Decimal) -> None:
    if value < Decimal("0"):
        raise ValidationError("Amount cannot be negative.")
