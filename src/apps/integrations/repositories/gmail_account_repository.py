from __future__ import annotations

from apps.integrations.models import GmailAccount


class GmailAccountRepository:
    @staticmethod
    def get_for_user(*, user_id: int, gmail_account_id: int | None = None) -> GmailAccount:
        queryset = GmailAccount.objects.filter(user_id=user_id)
        if gmail_account_id is not None:
            return queryset.get(id=gmail_account_id)
        return queryset.order_by("-connected_at").first()

    @staticmethod
    def list_for_user(*, user_id: int):
        return GmailAccount.objects.filter(user_id=user_id).order_by("-connected_at")

    @staticmethod
    def save(account: GmailAccount, *, update_fields: list[str] | None = None) -> GmailAccount:
        account.save(update_fields=update_fields)
        return account