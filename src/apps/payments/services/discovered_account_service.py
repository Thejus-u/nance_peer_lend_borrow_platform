from __future__ import annotations

from django.db import transaction
from django.db.models import F

from apps.audit.services import AuditEventService
from apps.payments.models import AccountType, DiscoveredAccount, DiscoveredAccountStatus


class DiscoveredAccountServiceError(Exception):
    """Base exception for discovered account operations."""


class DiscoveredAccountService:
    @classmethod
    @transaction.atomic
    def discover_account(
        cls,
        *,
        user_id: int,
        account_number: str,
        bank: str,
        account_type: str,
        increment_supporting_email_count: bool = False,
    ) -> DiscoveredAccount:
        cls._validate_account_type(account_type)

        account, created = DiscoveredAccount.objects.get_or_create(
            user_id=user_id,
            account_number=account_number.strip(),
            bank=bank.strip().upper(),
            account_type=account_type,
            defaults={"status": DiscoveredAccountStatus.UNLINKED},
        )
        if created:
            AuditEventService.record_state_change(
                entity_type="discovered_account",
                entity_id=account.id,
                field_name="status",
                from_state=None,
                to_state=account.status,
                actor_user_id=user_id,
                metadata={"action": "discovered_account.create"},
            )
            return account

        if increment_supporting_email_count:
            DiscoveredAccount.objects.filter(id=account.id).update(
                supporting_email_count=F("supporting_email_count") + 1,
            )
            account.refresh_from_db()
        return account

    @classmethod
    @transaction.atomic
    def link_account(cls, *, account_id: int, user_id: int) -> DiscoveredAccount:
        account = cls._get_owned_account(account_id=account_id, user_id=user_id)
        previous_status = account.status
        account.status = DiscoveredAccountStatus.LINKED
        account.save(update_fields=["status", "updated_at"])
        cls._record_status_change(
            account=account,
            from_status=previous_status,
            actor_user_id=user_id,
            action="discovered_account.link",
        )
        return account

    @classmethod
    @transaction.atomic
    def dismiss_account(cls, *, account_id: int, user_id: int) -> DiscoveredAccount:
        account = cls._get_owned_account(account_id=account_id, user_id=user_id)
        previous_status = account.status
        account.status = DiscoveredAccountStatus.DISMISSED
        account.save(update_fields=["status", "updated_at"])
        cls._record_status_change(
            account=account,
            from_status=previous_status,
            actor_user_id=user_id,
            action="discovered_account.dismiss",
        )
        return account

    @classmethod
    @transaction.atomic
    def unlink_account(cls, *, account_id: int, user_id: int) -> DiscoveredAccount:
        account = cls._get_owned_account(account_id=account_id, user_id=user_id)
        previous_status = account.status
        account.status = DiscoveredAccountStatus.UNLINKED
        account.save(update_fields=["status", "updated_at"])
        cls._record_status_change(
            account=account,
            from_status=previous_status,
            actor_user_id=user_id,
            action="discovered_account.unlink",
        )
        return account

    @staticmethod
    def _record_status_change(
        *,
        account: DiscoveredAccount,
        from_status: str | None,
        actor_user_id: int,
        action: str,
    ) -> None:
        if from_status == account.status:
            return

        AuditEventService.record_state_change(
            entity_type="discovered_account",
            entity_id=account.id,
            field_name="status",
            from_state=from_status,
            to_state=account.status,
            actor_user_id=actor_user_id,
            metadata={"action": action},
        )

    @staticmethod
    def _get_owned_account(*, account_id: int, user_id: int) -> DiscoveredAccount:
        try:
            return DiscoveredAccount.objects.get(id=account_id, user_id=user_id)
        except DiscoveredAccount.DoesNotExist as exc:
            raise DiscoveredAccountServiceError("Discovered account not found.") from exc

    @staticmethod
    def _validate_account_type(account_type: str) -> None:
        valid = {choice for choice, _ in AccountType.choices}
        if account_type not in valid:
            raise DiscoveredAccountServiceError("Invalid account type.")
