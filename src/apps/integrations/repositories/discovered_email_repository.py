from __future__ import annotations

from apps.integrations.models import DiscoveredEmail, GmailAccount


class DiscoveredEmailRepository:
    @staticmethod
    def upsert(
        *,
        gmail_account: GmailAccount,
        gmail_message_id: str,
        subject: str,
        sender: str,
        received_at,
        raw_payload: dict,
    ) -> tuple[DiscoveredEmail, bool]:
        return DiscoveredEmail.objects.update_or_create(
            gmail_account=gmail_account,
            gmail_message_id=gmail_message_id,
            defaults={
                "subject": subject,
                "sender": sender,
                "received_at": received_at,
                "raw_payload": raw_payload,
            },
        )

    @staticmethod
    def list_for_account(*, gmail_account: GmailAccount):
        return DiscoveredEmail.objects.filter(gmail_account=gmail_account)

    @staticmethod
    def count_for_account(*, gmail_account: GmailAccount) -> int:
        return DiscoveredEmail.objects.filter(gmail_account=gmail_account).count()