from __future__ import annotations

from celery import shared_task

from apps.integrations.models import GmailAccount
from apps.integrations.services.gmail_sync import GmailSyncService


@shared_task(name="integrations.sync_gmail_messages")
def sync_gmail_messages_task(gmail_account_id: int, max_results: int = 20, query: str | None = None) -> dict:
    account = GmailAccount.objects.get(id=gmail_account_id)
    return GmailSyncService.sync_messages(
        user_id=account.user_id,
        gmail_account_id=gmail_account_id,
        max_results=max_results,
        query=query,
    )