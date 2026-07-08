from __future__ import annotations

from datetime import date, timedelta

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.family.models import (
    Family,
    FamilyInvitation,
    FamilyInvitationStatus,
    FamilyMember,
    FamilyMemberRole,
)
from apps.loans.choices import LoanStatus
from apps.loans.models import Loan, Repayment, RepaymentStatus
from apps.notifications.models import Notification


class FamilyAPITestCase(APITestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            mobile_number="+14158880001",
            name="Family Owner",
            password="StrongPass123!",
        )
        self.invited = User.objects.create_user(
            mobile_number="+14158880002",
            name="Invited User",
            password="StrongPass123!",
        )
        self.rejected_user = User.objects.create_user(
            mobile_number="+14158880003",
            name="Rejected User",
            password="StrongPass123!",
        )
        self.outsider = User.objects.create_user(
            mobile_number="+14158880004",
            name="Family Outsider",
            password="StrongPass123!",
        )

        owner_login = self.client.post(
            reverse("accounts:login"),
            {"mobile_number": self.owner.mobile_number, "password": "StrongPass123!"},
            format="json",
        )
        self.owner_token = owner_login.data["access"]

        invited_login = self.client.post(
            reverse("accounts:login"),
            {"mobile_number": self.invited.mobile_number, "password": "StrongPass123!"},
            format="json",
        )
        self.invited_token = invited_login.data["access"]

        rejected_login = self.client.post(
            reverse("accounts:login"),
            {"mobile_number": self.rejected_user.mobile_number, "password": "StrongPass123!"},
            format="json",
        )
        self.rejected_token = rejected_login.data["access"]

        outsider_login = self.client.post(
            reverse("accounts:login"),
            {"mobile_number": self.outsider.mobile_number, "password": "StrongPass123!"},
            format="json",
        )
        self.outsider_token = outsider_login.data["access"]

    def _create_owner_family(self) -> Family:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        response = self.client.post(reverse("family:create"), {"name": "Core Family"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return Family.objects.get(id=response.data["id"])

    def test_current_returns_no_family_when_user_not_member(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.outsider_token}")

        response = self.client.get(reverse("family:current"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["has_family"], False)
        self.assertIsNone(response.data["family"])

    def test_create_family_allows_only_one_owned_family(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")

        first = self.client.post(reverse("family:create"), {"name": "Alpha"}, format="json")
        second = self.client.post(reverse("family:create"), {"name": "Beta"}, format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already own a family", second.data["detail"])

    def test_invitation_accept_flow_creates_membership_after_accept(self) -> None:
        family = self._create_owner_family()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        invite_response = self.client.post(
            reverse("family:create_invitation"),
            {"invited_user_id": self.invited.id},
            format="json",
        )

        self.assertEqual(invite_response.status_code, status.HTTP_201_CREATED)
        invitation_id = invite_response.data["id"]
        self.assertFalse(FamilyMember.objects.filter(family=family, user=self.invited).exists())

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.invited_token}")
        pending = self.client.get(reverse("family:invitations"))
        self.assertEqual(pending.status_code, status.HTTP_200_OK)
        self.assertEqual(len(pending.data), 1)

        accept = self.client.post(
            reverse("family:accept_invitation", kwargs={"invitation_id": invitation_id}),
            {},
            format="json",
        )
        self.assertEqual(accept.status_code, status.HTTP_200_OK)

        self.assertTrue(FamilyMember.objects.filter(family=family, user=self.invited).exists())
        invitation = FamilyInvitation.objects.get(id=invitation_id)
        self.assertEqual(invitation.status, FamilyInvitationStatus.ACCEPTED)

        self.assertTrue(
            Notification.objects.filter(
                user_id=self.invited.id,
                notification_type="family_invitation_sent",
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user_id=self.owner.id,
                notification_type="family_invitation_accepted",
            ).exists()
        )

    def test_invitation_reject_flow_does_not_create_membership(self) -> None:
        family = self._create_owner_family()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        invite_response = self.client.post(
            reverse("family:create_invitation"),
            {"invited_user_id": self.rejected_user.id},
            format="json",
        )
        invitation_id = invite_response.data["id"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.rejected_token}")
        reject = self.client.post(
            reverse("family:reject_invitation", kwargs={"invitation_id": invitation_id}),
            {},
            format="json",
        )

        self.assertEqual(reject.status_code, status.HTTP_200_OK)
        self.assertFalse(FamilyMember.objects.filter(family=family, user=self.rejected_user).exists())
        self.assertEqual(
            FamilyInvitation.objects.get(id=invitation_id).status,
            FamilyInvitationStatus.REJECTED,
        )
        self.assertTrue(
            Notification.objects.filter(
                user_id=self.owner.id,
                notification_type="family_invitation_rejected",
            ).exists()
        )

    def test_duplicate_pending_invitation_and_inviting_existing_member_are_rejected(self) -> None:
        family = self._create_owner_family()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        first = self.client.post(
            reverse("family:create_invitation"),
            {"invited_user_id": self.invited.id},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        duplicate_pending = self.client.post(
            reverse("family:create_invitation"),
            {"invited_user_id": self.invited.id},
            format="json",
        )
        self.assertEqual(duplicate_pending.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.invited_token}")
        self.client.post(
            reverse("family:accept_invitation", kwargs={"invitation_id": first.data["id"]}),
            {},
            format="json",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        invite_existing_member = self.client.post(
            reverse("family:create_invitation"),
            {"invited_user_id": self.invited.id},
            format="json",
        )
        self.assertEqual(invite_existing_member.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(FamilyMember.objects.filter(family=family, user=self.invited).exists())

    def test_only_owner_can_invite_or_remove_members(self) -> None:
        family = self._create_owner_family()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        invite = self.client.post(
            reverse("family:create_invitation"),
            {"invited_user_id": self.invited.id},
            format="json",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.invited_token}")
        self.client.post(
            reverse("family:accept_invitation", kwargs={"invitation_id": invite.data["id"]}),
            {},
            format="json",
        )

        member_invite_attempt = self.client.post(
            reverse("family:create_invitation"),
            {"invited_user_id": self.rejected_user.id},
            format="json",
        )
        self.assertEqual(member_invite_attempt.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        remove_member = self.client.post(
            reverse("family:remove_member"),
            {"member_user_id": self.invited.id},
            format="json",
        )
        self.assertEqual(remove_member.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(FamilyMember.objects.filter(family=family, user=self.invited).exists())
        self.assertTrue(
            Notification.objects.filter(
                user_id=self.invited.id,
                notification_type="family_member_removed",
            ).exists()
        )

    def test_current_ledger_requires_family_membership(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.outsider_token}")

        response = self.client.get(reverse("family:ledger"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not part of any family", response.data["detail"])

    def test_current_ledger_includes_member_positions(self) -> None:
        family = self._create_owner_family()
        FamilyMember.objects.create(family=family, user=self.invited, role=FamilyMemberRole.MEMBER)

        loan = Loan.objects.create(
            borrower=self.invited,
            lender=self.owner,
            status=LoanStatus.ACTIVE,
            principal_amount="500.00",
            currency="USD",
            interest_rate="5.00",
            repayment_term_months=6,
            starts_at=date.today(),
            ends_at=date.today() + timedelta(days=30),
            purpose="Family balance",
        )
        Repayment.objects.create(
            loan=loan,
            installment_number=1,
            due_date=date.today() + timedelta(days=10),
            amount_due="500.00",
            amount_paid="200.00",
            status=RepaymentStatus.PARTIAL,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_token}")
        response = self.client.get(reverse("family:ledger"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        owner_position = next(item for item in response.data["member_positions"] if item["user_id"] == self.owner.id)
        member_position = next(item for item in response.data["member_positions"] if item["user_id"] == self.invited.id)
        self.assertEqual(owner_position["total_lent"], "300.00")
        self.assertEqual(member_position["total_borrowed"], "300.00")
