from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.family.api.permissions import IsFamilyAuthenticatedAndActive
from apps.family.api.serializers import (
	FamilyCreateSerializer,
	FamilyInvitationDecisionSerializer,
	FamilyInvitationSerializer,
	FamilyInviteSerializer,
	FamilyMemberSerializer,
	FamilySerializer,
	FamilyLedgerEntrySerializer,
	FamilyRemoveMemberSerializer,
)
from apps.family.services.family_service import (
	FamilyNotFoundError,
	FamilyService,
	InvalidFamilyOperationError,
)


class FamilyInvitationAPIView(APIView):
	permission_classes = [IsFamilyAuthenticatedAndActive]

	def post(self, request: Request, *args, **kwargs) -> Response:
		serializer = FamilyInviteSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		try:
			invitation = serializer.save(actor_user_id=request.user.id)
		except FamilyNotFoundError as exc:
			return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
		return Response(FamilyInvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)

	def get(self, request: Request, *args, **kwargs) -> Response:
		invitations = FamilyService.list_invitations_for_user(user_id=request.user.id)
		return Response(FamilyInvitationSerializer(invitations, many=True).data, status=status.HTTP_200_OK)


class FamilyCreateAPIView(APIView):
	permission_classes = [IsFamilyAuthenticatedAndActive]

	def post(self, request: Request, *args, **kwargs) -> Response:
		serializer = FamilyCreateSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		family = serializer.save(owner_user_id=request.user.id)
		return Response(FamilySerializer(family).data, status=status.HTTP_201_CREATED)


class FamilyCurrentAPIView(APIView):
	permission_classes = [IsFamilyAuthenticatedAndActive]

	def get(self, request: Request, *args, **kwargs) -> Response:
		context = FamilyService.get_current_family_context(user_id=request.user.id)
		payload = {
			"has_family": context["has_family"],
			"role": context["role"],
			"can_manage_members": context["can_manage_members"],
			"family": FamilySerializer(context["family"]).data if context["family"] else None,
			"members": FamilyMemberSerializer(context["members"], many=True).data,
		}
		return Response(payload, status=status.HTTP_200_OK)


class FamilyInvitationAcceptAPIView(APIView):
	permission_classes = [IsFamilyAuthenticatedAndActive]

	def post(self, request: Request, invitation_id: int, *args, **kwargs) -> Response:
		serializer = FamilyInvitationDecisionSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		try:
			invitation = serializer.save_accept(invitation_id=invitation_id, actor_user_id=request.user.id)
		except FamilyNotFoundError as exc:
			return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
		return Response(FamilyInvitationSerializer(invitation).data, status=status.HTTP_200_OK)


class FamilyInvitationRejectAPIView(APIView):
	permission_classes = [IsFamilyAuthenticatedAndActive]

	def post(self, request: Request, invitation_id: int, *args, **kwargs) -> Response:
		serializer = FamilyInvitationDecisionSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		try:
			invitation = serializer.save_reject(invitation_id=invitation_id, actor_user_id=request.user.id)
		except FamilyNotFoundError as exc:
			return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
		return Response(FamilyInvitationSerializer(invitation).data, status=status.HTTP_200_OK)


class FamilyRemoveMemberAPIView(APIView):
	permission_classes = [IsFamilyAuthenticatedAndActive]

	def post(self, request: Request, *args, **kwargs) -> Response:
		serializer = FamilyRemoveMemberSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		try:
			serializer.save(actor_user_id=request.user.id)
		except FamilyNotFoundError as exc:
			return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
		return Response(status=status.HTTP_204_NO_CONTENT)


class FamilyLedgerAPIView(APIView):
	permission_classes = [IsFamilyAuthenticatedAndActive]

	def get(self, request: Request, *args, **kwargs) -> Response:
		try:
			ledger = FamilyService.get_family_ledger(
				actor_user_id=request.user.id,
			)
		except FamilyNotFoundError as exc:
			return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
		except InvalidFamilyOperationError as exc:
			return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

		data = FamilyLedgerEntrySerializer(ledger["entries"], many=True).data
		return Response(
			{
				"total_amount": ledger["total_amount"],
				"entries": data,
				"member_positions": ledger["member_positions"],
				"consolidated_obligations": ledger["consolidated_obligations"],
			},
			status=status.HTTP_200_OK,
		)
