from django.urls import path

from apps.family.api.views import (
	FamilyCreateAPIView,
	FamilyCurrentAPIView,
	FamilyInvitationAcceptAPIView,
	FamilyInvitationAPIView,
	FamilyInvitationRejectAPIView,
	FamilyLedgerAPIView,
	FamilyRemoveMemberAPIView,
)

app_name = "family"

urlpatterns = [
	path("create/", FamilyCreateAPIView.as_view(), name="create"),
	path("current/", FamilyCurrentAPIView.as_view(), name="current"),
	path("current/ledger/", FamilyLedgerAPIView.as_view(), name="ledger"),
	path("current/members/remove/", FamilyRemoveMemberAPIView.as_view(), name="remove_member"),
	path("invitations/", FamilyInvitationAPIView.as_view(), name="invitations"),
	path("invitations/create/", FamilyInvitationAPIView.as_view(), name="create_invitation"),
	path("invitations/<int:invitation_id>/accept/", FamilyInvitationAcceptAPIView.as_view(), name="accept_invitation"),
	path("invitations/<int:invitation_id>/reject/", FamilyInvitationRejectAPIView.as_view(), name="reject_invitation"),
]
