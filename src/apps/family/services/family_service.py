from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import QuerySet, Sum
from django.utils import timezone

from apps.family.models import (
    Family,
    FamilyInvitation,
    FamilyInvitationStatus,
    FamilyLedgerAction,
    FamilyLedgerEntry,
    FamilyMember,
    FamilyMemberRole,
)
from apps.loans.choices import LoanStatus
from apps.loans.models import Loan


class FamilyServiceError(Exception):
    """Base service-layer exception for family operations."""


class InvalidFamilyOperationError(FamilyServiceError):
    """Raised when a family operation breaks business constraints."""


class FamilyNotFoundError(FamilyServiceError):
    """Raised when a family or invitation does not exist."""


class FamilyService:
    @classmethod
    def get_current_family_for_user(cls, *, user_id: int) -> Family | None:
        membership = (
            FamilyMember.objects.select_related("family")
            .filter(user_id=user_id)
            .order_by("id")
            .first()
        )
        if membership is not None:
            return membership.family

        return Family.objects.filter(owner_id=user_id).order_by("id").first()

    @classmethod
    def get_current_family_context(cls, *, user_id: int) -> dict[str, object]:
        family = cls.get_current_family_for_user(user_id=user_id)
        if family is None:
            return {
                "has_family": False,
                "family": None,
                "role": None,
                "can_manage_members": False,
                "members": [],
            }

        role = cls._resolve_user_role(family=family, user_id=user_id)
        if role is None:
            raise InvalidFamilyOperationError("User is not a member of the current family.")

        members = list(
            FamilyMember.objects.filter(family_id=family.id)
            .select_related("user")
            .order_by("joined_at")
        )

        return {
            "has_family": True,
            "family": family,
            "role": role,
            "can_manage_members": role in {FamilyMemberRole.OWNER, FamilyMemberRole.ADMIN},
            "members": members,
        }

    @classmethod
    def list_invitations_for_user(cls, *, user_id: int) -> QuerySet[FamilyInvitation]:
        return FamilyInvitation.objects.filter(
            invited_user_id=user_id,
            status=FamilyInvitationStatus.PENDING,
        ).select_related("family", "invited_by")

    @classmethod
    @transaction.atomic
    def create_family(
        cls,
        *,
        owner_user_id: int,
        name: str,
    ) -> Family:
        normalized_name = name.strip()
        if not normalized_name:
            raise InvalidFamilyOperationError("Family name is required.")

        if Family.objects.select_for_update().filter(owner_id=owner_user_id).exists():
            raise InvalidFamilyOperationError("You already own a family.")

        family = Family.objects.create(name=normalized_name, owner_id=owner_user_id)
        FamilyMember.objects.create(
            family=family,
            user_id=owner_user_id,
            role=FamilyMemberRole.OWNER,
        )
        return family

    @classmethod
    @transaction.atomic
    def create_invitation(
        cls,
        *,
        actor_user_id: int,
        invited_user_id: int,
    ) -> FamilyInvitation:
        family = cls._get_actor_managed_family_for_update(actor_user_id=actor_user_id)

        if invited_user_id == actor_user_id:
            raise InvalidFamilyOperationError("You cannot invite yourself.")

        user_model = get_user_model()
        if not user_model.objects.filter(id=invited_user_id).exists():
            raise InvalidFamilyOperationError("Invited user does not exist.")

        if FamilyMember.objects.select_for_update().filter(
            family_id=family.id,
            user_id=invited_user_id,
        ).exists():
            raise InvalidFamilyOperationError("User is already a member of this family.")

        if FamilyInvitation.objects.select_for_update().filter(
            family_id=family.id,
            invited_user_id=invited_user_id,
            status=FamilyInvitationStatus.PENDING,
        ).exists():
            raise InvalidFamilyOperationError("A pending invitation already exists for this user.")

        invitation = FamilyInvitation.objects.create(
            family_id=family.id,
            invited_user_id=invited_user_id,
            invited_by_id=actor_user_id,
            status=FamilyInvitationStatus.PENDING,
        )

        cls._queue_notification_on_commit(
            user_id=invited_user_id,
            title="Family Invitation",
            message=f"You have been invited to join family '{family.name}'.",
            notification_type="family_invitation_sent",
            dedupe_key=f"family-invitation:{invitation.id}",
            payload={
                "family_id": family.id,
                "invitation_id": invitation.id,
                "invited_by_user_id": actor_user_id,
            },
        )
        return invitation

    @classmethod
    @transaction.atomic
    def accept_invitation(
        cls,
        *,
        invitation_id: int,
        actor_user_id: int,
    ) -> FamilyInvitation:
        invitation = cls._get_pending_invitation_for_update(invitation_id=invitation_id)
        if invitation.invited_user_id != actor_user_id:
            raise InvalidFamilyOperationError("You can only accept your own invitations.")

        if FamilyMember.objects.select_for_update().filter(
            family_id=invitation.family_id,
            user_id=actor_user_id,
        ).exists():
            raise InvalidFamilyOperationError("You are already a member of this family.")

        FamilyMember.objects.create(
            family_id=invitation.family_id,
            user_id=actor_user_id,
            role=FamilyMemberRole.MEMBER,
        )

        FamilyLedgerEntry.objects.create(
            family_id=invitation.family_id,
            actor_id=actor_user_id,
            member_id=actor_user_id,
            action=FamilyLedgerAction.MEMBER_ADDED,
            amount=0,
            note="Invitation accepted; member added.",
        )

        invitation.status = FamilyInvitationStatus.ACCEPTED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])

        cls._queue_notification_on_commit(
            user_id=invitation.invited_by_id,
            title="Invitation Accepted",
            message="Your family invitation was accepted.",
            notification_type="family_invitation_accepted",
            dedupe_key=f"family-invitation-accepted:{invitation.id}",
            payload={
                "family_id": invitation.family_id,
                "invitation_id": invitation.id,
                "user_id": actor_user_id,
            },
        )
        return invitation

    @classmethod
    @transaction.atomic
    def reject_invitation(
        cls,
        *,
        invitation_id: int,
        actor_user_id: int,
    ) -> FamilyInvitation:
        invitation = cls._get_pending_invitation_for_update(invitation_id=invitation_id)
        if invitation.invited_user_id != actor_user_id:
            raise InvalidFamilyOperationError("You can only reject your own invitations.")

        invitation.status = FamilyInvitationStatus.REJECTED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])

        cls._queue_notification_on_commit(
            user_id=invitation.invited_by_id,
            title="Invitation Rejected",
            message="Your family invitation was rejected.",
            notification_type="family_invitation_rejected",
            dedupe_key=f"family-invitation-rejected:{invitation.id}",
            payload={
                "family_id": invitation.family_id,
                "invitation_id": invitation.id,
                "user_id": actor_user_id,
            },
        )
        return invitation

    @classmethod
    @transaction.atomic
    def remove_member(
        cls,
        *,
        actor_user_id: int,
        member_user_id: int,
    ) -> None:
        family = cls._get_actor_managed_family_for_update(actor_user_id=actor_user_id)

        if family.owner_id == member_user_id:
            raise InvalidFamilyOperationError("Family owner cannot be removed.")

        membership = FamilyMember.objects.select_for_update().filter(
            family_id=family.id,
            user_id=member_user_id,
        ).first()
        if membership is None:
            raise InvalidFamilyOperationError("User is not a member of this family.")

        membership.delete()

        FamilyLedgerEntry.objects.create(
            family_id=family.id,
            actor_id=actor_user_id,
            member_id=member_user_id,
            action=FamilyLedgerAction.MEMBER_REMOVED,
            amount=0,
            note="Family member removed.",
        )

        cls._queue_notification_on_commit(
            user_id=member_user_id,
            title="Removed From Family",
            message=f"You were removed from family '{family.name}'.",
            notification_type="family_member_removed",
            dedupe_key=f"family-member-removed:{family.id}:{member_user_id}",
            payload={"family_id": family.id, "user_id": member_user_id},
        )

    @classmethod
    def get_family_ledger(
        cls,
        *,
        actor_user_id: int,
    ) -> dict[str, object]:
        family = cls.get_current_family_for_user(user_id=actor_user_id)
        if family is None:
            raise InvalidFamilyOperationError("You are not part of any family.")

        cls._ensure_actor_is_member(family=family, actor_user_id=actor_user_id)

        entries = FamilyLedgerEntry.objects.filter(family_id=family.id).select_related("actor", "member")
        total = entries.aggregate(total=Sum("amount"))["total"]
        member_positions, consolidated_obligations = cls._build_member_positions(family=family)
        return {
            "entries": entries,
            "total_amount": str(total or 0),
            "member_positions": member_positions,
            "consolidated_obligations": consolidated_obligations,
        }

    @staticmethod
    def _build_member_positions(*, family: Family) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        member_ids = set(FamilyMember.objects.filter(family_id=family.id).values_list("user_id", flat=True))
        member_ids.add(family.owner_id)

        members = {member.id: member for member in family.owner.__class__.objects.filter(id__in=member_ids)}
        positions = {
            member_id: {
                "user_id": member_id,
                "mobile_number": members[member_id].mobile_number,
                "name": members[member_id].name,
                "total_lent": 0,
                "total_borrowed": 0,
                "net_position": 0,
            }
            for member_id in member_ids
        }
        consolidated_obligations: list[dict[str, object]] = []

        loans = (
            Loan.objects.filter(
                borrower_id__in=member_ids,
                lender_id__in=member_ids,
            )
            .exclude(
                status__in=[
                    LoanStatus.DRAFT,
                    LoanStatus.PENDING_INVITE,
                    LoanStatus.PENDING_REVIEW,
                    LoanStatus.REJECTED,
                    LoanStatus.CANCELLED,
                ]
            )
            .prefetch_related("repayments")
        )

        for loan in loans:
            paid_amount = sum(repayment.amount_paid for repayment in loan.repayments.all())
            outstanding = max(loan.principal_amount - paid_amount, 0)
            if outstanding <= 0:
                continue

            positions[loan.lender_id]["total_lent"] += outstanding
            positions[loan.borrower_id]["total_borrowed"] += outstanding
            consolidated_obligations.append(
                {
                    "from_user_id": loan.borrower_id,
                    "to_user_id": loan.lender_id,
                    "amount": str(outstanding),
                    "loan_id": loan.id,
                }
            )

        member_positions: list[dict[str, object]] = []
        for member_id in sorted(member_ids):
            positions[member_id]["net_position"] = (
                positions[member_id]["total_lent"] - positions[member_id]["total_borrowed"]
            )
            member_positions.append(
                {
                    **positions[member_id],
                    "total_lent": str(positions[member_id]["total_lent"]),
                    "total_borrowed": str(positions[member_id]["total_borrowed"]),
                    "net_position": str(positions[member_id]["net_position"]),
                }
            )

        return member_positions, consolidated_obligations

    @staticmethod
    def _ensure_actor_can_manage_members(*, family: Family, actor_user_id: int) -> None:
        role = FamilyService._resolve_user_role(family=family, user_id=actor_user_id)
        if role in {FamilyMemberRole.OWNER, FamilyMemberRole.ADMIN}:
            return
        raise InvalidFamilyOperationError("Only family owner/admin can manage family members.")

    @staticmethod
    def _ensure_actor_is_member(*, family: Family, actor_user_id: int) -> None:
        if FamilyService._resolve_user_role(family=family, user_id=actor_user_id) is not None:
            return
        raise InvalidFamilyOperationError("Only family members can view the family ledger.")

    @staticmethod
    def _resolve_user_role(*, family: Family, user_id: int) -> str | None:
        if family.owner_id == user_id:
            return FamilyMemberRole.OWNER

        membership = FamilyMember.objects.filter(family_id=family.id, user_id=user_id).first()
        if membership is None:
            return None
        return membership.role

    @classmethod
    def _get_actor_managed_family_for_update(cls, *, actor_user_id: int) -> Family:
        owned_family = (
            Family.objects.select_for_update()
            .filter(owner_id=actor_user_id)
            .order_by("id")
            .first()
        )
        if owned_family is not None:
            return owned_family

        current_family = cls.get_current_family_for_user(user_id=actor_user_id)
        if current_family is None:
            raise InvalidFamilyOperationError("You are not part of any family.")

        family = Family.objects.select_for_update().get(id=current_family.id)
        cls._ensure_actor_can_manage_members(family=family, actor_user_id=actor_user_id)
        return family

    @staticmethod
    def _get_pending_invitation_for_update(*, invitation_id: int) -> FamilyInvitation:
        try:
            invitation = FamilyInvitation.objects.select_for_update().get(id=invitation_id)
        except FamilyInvitation.DoesNotExist as exc:
            raise FamilyNotFoundError("Invitation not found.") from exc

        if invitation.status != FamilyInvitationStatus.PENDING:
            raise InvalidFamilyOperationError("Invitation is no longer pending.")

        return invitation

    @staticmethod
    def _queue_notification_on_commit(
        *,
        user_id: int | None,
        title: str,
        message: str,
        notification_type: str,
        dedupe_key: str,
        payload: dict[str, object],
    ) -> None:
        if not user_id:
            return
        from apps.notifications.tasks import queue_notification_task

        queue_notification_task.delay(
            user_id=user_id,
            channel="in_app",
            title=title,
            message=message,
            notification_type=notification_type,
            dedupe_key=dedupe_key,
            payload=payload,
        )
