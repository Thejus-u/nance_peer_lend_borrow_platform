from __future__ import annotations

from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.loans.models import Loan


def publish_loan_event(*, loan: Loan, event: str, actor_user_id: int | None = None) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    payload = {
        "type": "loan_event",
        "event": event,
        "actor_user_id": actor_user_id,
        "timestamp": timezone.now().isoformat(),
        "loan": {
            "id": loan.id,
            "public_id": str(loan.public_id),
            "status": loan.status,
            "borrower_id": loan.borrower_id,
            "lender_id": loan.lender_id,
            "principal_amount": str(loan.principal_amount),
            "currency": loan.currency,
        },
    }

    group_names = {f"loan_{loan.id}", f"loan_user_{loan.borrower_id}"}
    if loan.lender_id:
        group_names.add(f"loan_user_{loan.lender_id}")

    print("----------------------------------------------------")
    print("Publishing event:", event)
    print("Groups:", sorted(group_names))
    print("----------------------------------------------------")

    for group_name in group_names:
        print(f"Sending {event} to {group_name}")
        async_to_sync(channel_layer.group_send)(group_name, payload)
