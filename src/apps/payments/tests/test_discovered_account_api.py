from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.payments.models import DiscoveredAccountStatus


class DiscoveredAccountAPITestCase(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            mobile_number="+14159990001",
            name="Discovery User",
            password="StrongPass123!",
        )

        login_response = self.client.post(
            reverse("accounts:login"),
            {"mobile_number": self.user.mobile_number, "password": "StrongPass123!"},
            format="json",
        )
        self.access_token = login_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_discover_account_creates_unlinked_record(self) -> None:
        payload = {
            "account_number": "1234567890",
            "bank": "Acme Bank",
            "account_type": "savings",
        }
        response = self.client.post(reverse("payments:discover_account"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], DiscoveredAccountStatus.UNLINKED)

    def test_linked_status_action(self) -> None:
        discover_response = self.client.post(
            reverse("payments:discover_account"),
            {
                "account_number": "111122223333",
                "bank": "Acme Bank",
                "account_type": "current",
            },
            format="json",
        )
        account_id = discover_response.data["id"]

        response = self.client.post(
            reverse(
                "payments:discovered_account_action",
                kwargs={"account_id": account_id, "action": "linked"},
            ),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], DiscoveredAccountStatus.LINKED)

    def test_dismissed_status_action(self) -> None:
        discover_response = self.client.post(
            reverse("payments:discover_account"),
            {
                "account_number": "222233334444",
                "bank": "Acme Bank",
                "account_type": "wallet",
            },
            format="json",
        )
        account_id = discover_response.data["id"]

        response = self.client.post(
            reverse(
                "payments:discovered_account_action",
                kwargs={"account_id": account_id, "action": "dismissed"},
            ),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], DiscoveredAccountStatus.DISMISSED)

    def test_unlinked_status_action(self) -> None:
        discover_response = self.client.post(
            reverse("payments:discover_account"),
            {
                "account_number": "333344445555",
                "bank": "Acme Bank",
                "account_type": "other",
            },
            format="json",
        )
        account_id = discover_response.data["id"]

        self.client.post(
            reverse(
                "payments:discovered_account_action",
                kwargs={"account_id": account_id, "action": "linked"},
            ),
            {},
            format="json",
        )

        response = self.client.post(
            reverse(
                "payments:discovered_account_action",
                kwargs={"account_id": account_id, "action": "unlinked"},
            ),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], DiscoveredAccountStatus.UNLINKED)

    def test_list_discovered_accounts(self) -> None:
        self.client.post(
            reverse("payments:discover_account"),
            {
                "account_number": "777788889999",
                "bank": "Acme Bank",
                "account_type": "savings",
            },
            format="json",
        )

        response = self.client.get(reverse("payments:discovered_accounts"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["status"], DiscoveredAccountStatus.UNLINKED)

    def test_list_discovered_accounts_filters_by_status(self) -> None:
        first = self.client.post(
            reverse("payments:discover_account"),
            {
                "account_number": "1212121212",
                "bank": "Acme Bank",
                "account_type": "savings",
            },
            format="json",
        )
        second = self.client.post(
            reverse("payments:discover_account"),
            {
                "account_number": "3434343434",
                "bank": "Acme Bank",
                "account_type": "current",
            },
            format="json",
        )
        self.client.post(
            reverse(
                "payments:discovered_account_action",
                kwargs={"account_id": second.data["id"], "action": "dismissed"},
            ),
            {},
            format="json",
        )

        default_response = self.client.get(reverse("payments:discovered_accounts"))
        dismissed_response = self.client.get(f"{reverse('payments:discovered_accounts')}?status=dismissed")

        self.assertEqual(default_response.status_code, status.HTTP_200_OK)
        self.assertEqual(default_response.data["count"], 1)
        self.assertEqual(default_response.data["results"][0]["id"], first.data["id"])
        self.assertEqual(dismissed_response.status_code, status.HTTP_200_OK)
        self.assertEqual(dismissed_response.data["count"], 1)
        self.assertEqual(dismissed_response.data["results"][0]["status"], DiscoveredAccountStatus.DISMISSED)
