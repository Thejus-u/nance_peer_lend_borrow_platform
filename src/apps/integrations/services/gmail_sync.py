from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.integrations.models import GmailAccount
from apps.integrations.repositories import DiscoveredEmailRepository, GmailAccountRepository
from apps.integrations.services.gmail_api import GmailAPIService
from apps.integrations.services.gmail_oauth import GmailOAuthService
from apps.integrations.services.gmail_parser import GmailParserService
from apps.payments.services.gmail_ingestion_service import GmailIngestionService


class GmailSyncService:
    @classmethod
    def sync_messages(
        cls,
        *,
        user_id: int,
        gmail_account_id: int | None = None,
        max_results: int = 20,
        query: str | None = None,
    ) -> dict[str, int | str | None]:
        account = GmailAccountRepository.get_for_user(user_id=user_id, gmail_account_id=gmail_account_id)
        if account is None:
            raise GmailAccount.DoesNotExist("Gmail account is not connected.")

        account = GmailOAuthService.ensure_access_token(account=account)
        access_token = account.get_access_token()
        messages = GmailAPIService.list_messages(
            access_token=access_token,
            max_results=max_results,
            query=query,
        )

        synced_count = 0
        parsed_count = 0
        discovered_account_count = 0
        ignored_count = 0

        for message in messages:
            payload = GmailAPIService.fetch_message(access_token=access_token, message_id=message["id"])
            metadata = GmailAPIService.extract_metadata(payload)
            body_text = GmailAPIService.decode_mime_body(payload)
            email_record, created = DiscoveredEmailRepository.upsert(
                gmail_account=account,
                gmail_message_id=message["id"],
                subject=str(metadata.get("subject") or ""),
                sender=str(metadata.get("sender") or ""),
                received_at=metadata.get("received_at"),
                raw_payload=payload,
            )
            synced_count += 1

            if created or not email_record.processed:
                parsed_email = GmailParserService.parse_transaction_email(
                    sender=str(metadata.get("sender") or ""),
                    subject=str(metadata.get("subject") or ""),
                    body=body_text,
                    received_at=metadata.get("received_at"),
                )
                stats = GmailIngestionService.ingest_message(
                    user_id=user_id,
                    gmail_message_id=message["id"],
                    sender_email=str(metadata.get("sender") or ""),
                    subject=str(metadata.get("subject") or ""),
                    body=body_text,
                    received_at=metadata.get("received_at"),
                )
                parsed_count += stats.transaction_count
                discovered_account_count += stats.discovered_account_count
                ignored_count += stats.ignored_count
                email_record.processed = parsed_email is not None or stats.ignored_count >= 0
                email_record.save(update_fields=["processed", "updated_at"])

        with transaction.atomic():
            account.last_sync_at = timezone.now()
            account.save(update_fields=["last_sync_at", "updated_at"])

        return {
            "gmail_account_id": account.id,
            "synced_count": synced_count,
            "parsed_count": parsed_count,
            "discovered_account_count": discovered_account_count,
            "ignored_count": ignored_count,
            "fetched_email_count": DiscoveredEmailRepository.count_for_account(gmail_account=account),
            "last_sync": account.last_sync_at.isoformat() if account.last_sync_at else None,
        }