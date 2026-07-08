from __future__ import annotations

from apps.integrations.models import GmailAccount
from apps.integrations.repositories import DiscoveredEmailRepository, GmailAccountRepository


class GmailSelector:
    @staticmethod
    def get_status(*, user_id: int) -> dict[str, object]:
        account = GmailAccountRepository.get_for_user(user_id=user_id)
        if account is None:
            return {
                "connected": False,
                "email": None,
                "last_sync": None,
                "fetched_email_count": 0,
            }

        return {
            "connected": True,
            "email": account.email,
            "last_sync": account.last_sync_at,
            "fetched_email_count": DiscoveredEmailRepository.count_for_account(gmail_account=account),
        }

    @staticmethod
    def list_messages(*, user_id: int):
        account = GmailAccountRepository.get_for_user(user_id=user_id)
        if account is None:
            return GmailAccount.objects.none()
        return account.discovered_emails.all()