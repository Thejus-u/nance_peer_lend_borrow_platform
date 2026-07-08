from __future__ import annotations

from rest_framework import serializers

from apps.family.models import Family, FamilyInvitation, FamilyLedgerEntry, FamilyMember
from apps.family.services.family_service import FamilyService, InvalidFamilyOperationError


class FamilyMemberSerializer(serializers.ModelSerializer):
	class Meta:
		model = FamilyMember
		fields = ("id", "family", "user", "role", "joined_at")
		read_only_fields = fields


class FamilySerializer(serializers.ModelSerializer):
	created_by = serializers.IntegerField(source="owner_id", read_only=True)

	class Meta:
		model = Family
		fields = ("id", "name", "created_by", "created_at")
		read_only_fields = fields


class FamilyInvitationSerializer(serializers.ModelSerializer):
	class Meta:
		model = FamilyInvitation
		fields = (
			"id",
			"family",
			"invited_user",
			"invited_by",
			"status",
			"created_at",
			"responded_at",
		)
		read_only_fields = fields


class FamilyCreateSerializer(serializers.Serializer):
	name = serializers.CharField(max_length=255)

	def save(self, *, owner_user_id: int) -> Family:
		try:
			return FamilyService.create_family(
				owner_user_id=owner_user_id,
				name=self.validated_data["name"],
			)
		except InvalidFamilyOperationError as exc:
			raise serializers.ValidationError({"detail": str(exc)}) from exc


class FamilyInviteSerializer(serializers.Serializer):
	invited_user_id = serializers.IntegerField(min_value=1)

	def save(self, *, actor_user_id: int) -> FamilyInvitation:
		try:
			return FamilyService.create_invitation(
				actor_user_id=actor_user_id,
				invited_user_id=self.validated_data["invited_user_id"],
			)
		except InvalidFamilyOperationError as exc:
			raise serializers.ValidationError({"detail": str(exc)}) from exc


class FamilyRemoveMemberSerializer(serializers.Serializer):
	member_user_id = serializers.IntegerField(min_value=1)

	def save(self, *, actor_user_id: int) -> None:
		try:
			FamilyService.remove_member(
				actor_user_id=actor_user_id,
				member_user_id=self.validated_data["member_user_id"],
			)
		except InvalidFamilyOperationError as exc:
			raise serializers.ValidationError({"detail": str(exc)}) from exc


class FamilyInvitationDecisionSerializer(serializers.Serializer):
	def save_accept(self, *, invitation_id: int, actor_user_id: int) -> FamilyInvitation:
		try:
			return FamilyService.accept_invitation(
				invitation_id=invitation_id,
				actor_user_id=actor_user_id,
			)
		except InvalidFamilyOperationError as exc:
			raise serializers.ValidationError({"detail": str(exc)}) from exc

	def save_reject(self, *, invitation_id: int, actor_user_id: int) -> FamilyInvitation:
		try:
			return FamilyService.reject_invitation(
				invitation_id=invitation_id,
				actor_user_id=actor_user_id,
			)
		except InvalidFamilyOperationError as exc:
			raise serializers.ValidationError({"detail": str(exc)}) from exc


class FamilyLedgerEntrySerializer(serializers.ModelSerializer):
	class Meta:
		model = FamilyLedgerEntry
		fields = (
			"id",
			"family",
			"actor",
			"member",
			"action",
			"amount",
			"note",
			"created_at",
		)
		read_only_fields = fields
