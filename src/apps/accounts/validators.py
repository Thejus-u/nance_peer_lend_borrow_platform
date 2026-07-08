from django.core.exceptions import ValidationError


def validate_mobile_number(value: str) -> None:
    """Validate mobile numbers using E.164-compatible format."""
    if not value:
        raise ValidationError("Mobile number is required.")

    if not value.startswith("+"):
        raise ValidationError("Mobile number must start with '+'.")

    digits = value[1:]
    if not digits.isdigit():
        raise ValidationError("Mobile number must contain only digits after '+'.")

    if len(digits) < 8 or len(digits) > 15:
        raise ValidationError("Mobile number must contain between 8 and 15 digits.")


def validate_gmail_address(value: str) -> None:
    """Ensure connected Gmail account uses a gmail.com address."""
    if not value:
        raise ValidationError("Gmail address is required.")

    normalized = value.strip().lower()
    if not normalized.endswith("@gmail.com"):
        raise ValidationError("Only @gmail.com accounts are allowed.")
