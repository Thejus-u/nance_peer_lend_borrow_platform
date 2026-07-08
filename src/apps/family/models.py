from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models import Q


class FamilyMemberRole(models.TextChoices):
	OWNER = "owner", "Owner"
	ADMIN = "admin", "Admin"
	MEMBER = "member", "Member"


class FamilyInvitationStatus(models.TextChoices):
	PENDING = "pending", "Pending"
	ACCEPTED = "accepted", "Accepted"
	REJECTED = "rejected", "Rejected"


class FamilyLedgerAction(models.TextChoices):
	MEMBER_ADDED = "member_added", "Member Added"
	MEMBER_REMOVED = "member_removed", "Member Removed"


class Family(models.Model):
	name = models.CharField(max_length=255)
	owner = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="owned_families",
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-created_at"]
		indexes = [
			models.Index(fields=["owner"], name="family_owner_idx"),
			models.Index(fields=["created_at"], name="family_created_at_idx"),
		]

	def __str__(self) -> str:
		return f"{self.name} ({self.owner_id})"


class FamilyMember(models.Model):
	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="memberships")
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="family_memberships",
	)
	role = models.CharField(max_length=20, choices=FamilyMemberRole.choices, default=FamilyMemberRole.MEMBER)
	joined_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["family_id", "joined_at"]
		constraints = [
			models.UniqueConstraint(
				fields=["family", "user"],
				name="family_member_unique_per_family",
			)
		]
		indexes = [
			models.Index(fields=["family", "role"], name="family_member_family_role_idx"),
			models.Index(fields=["user"], name="family_member_user_idx"),
		]

	def __str__(self) -> str:
		return f"{self.family_id}:{self.user_id}:{self.role}"


class FamilyInvitation(models.Model):
	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="invitations")
	invited_user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="family_invitations",
	)
	invited_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="family_sent_invitations",
	)
	status = models.CharField(
		max_length=20,
		choices=FamilyInvitationStatus.choices,
		default=FamilyInvitationStatus.PENDING,
		db_index=True,
	)
	created_at = models.DateTimeField(auto_now_add=True)
	responded_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ["-created_at"]
		constraints = [
			models.UniqueConstraint(
				fields=["family", "invited_user"],
				condition=Q(status=FamilyInvitationStatus.PENDING),
				name="family_pending_invitation_unique",
			)
		]
		indexes = [
			models.Index(fields=["family", "status"], name="family_inv_family_status_idx"),
			models.Index(fields=["invited_user", "status"], name="family_inv_user_status_idx"),
		]

	def __str__(self) -> str:
		return f"{self.family_id}:{self.invited_user_id}:{self.status}"


class FamilyLedgerEntry(models.Model):
	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="ledger_entries")
	actor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="family_ledger_actor_entries",
	)
	member = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="family_ledger_member_entries",
	)
	action = models.CharField(max_length=30, choices=FamilyLedgerAction.choices)
	amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
	note = models.CharField(max_length=500, blank=True, validators=[MaxLengthValidator(500)])
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]
		indexes = [
			models.Index(fields=["family", "created_at"], name="fam_ledger_family_created_idx"),
			models.Index(fields=["action"], name="family_ledger_action_idx"),
		]

	def __str__(self) -> str:
		return f"{self.family_id}:{self.action}:{self.amount}"
