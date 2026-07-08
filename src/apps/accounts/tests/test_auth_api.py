from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User


class AuthenticationAPITestCase(APITestCase):
    def setUp(self) -> None:
        self.register_url = reverse("accounts:register")
        self.login_url = reverse("accounts:login")
        self.refresh_url = reverse("accounts:token_refresh")
        self.current_user_url = reverse("accounts:current_user")
        self.logout_url = reverse("accounts:logout")

    def test_register_creates_user_and_returns_user_payload(self) -> None:
        payload = {
            "mobile_number": "+14155550101",
            "name": "Alice Doe",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "gmail_address": "alice@gmail.com",
        }

        response = self.client.post(self.register_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.get()
        self.assertEqual(user.mobile_number, payload["mobile_number"])
        self.assertEqual(user.gmail_accounts.count(), 1)

    def test_login_returns_jwt_pair(self) -> None:
        user = User.objects.create_user(
            mobile_number="+14155550102",
            name="Bob Smith",
            password="StrongPass123!",
        )

        payload = {
            "mobile_number": user.mobile_number,
            "password": "StrongPass123!",
        }

        response = self.client.post(self.login_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("user", response.data)

    def test_refresh_token_returns_new_access_token(self) -> None:
        user = User.objects.create_user(
            mobile_number="+14155550103",
            name="Charlie Lee",
            password="StrongPass123!",
        )
        login_response = self.client.post(
            self.login_url,
            {"mobile_number": user.mobile_number, "password": "StrongPass123!"},
            format="json",
        )

        refresh_response = self.client.post(
            self.refresh_url,
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)

    def test_current_user_requires_authentication(self) -> None:
        response = self.client.get(self.current_user_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_current_user_returns_authenticated_user(self) -> None:
        user = User.objects.create_user(
            mobile_number="+14155550104",
            name="Dana Gray",
            password="StrongPass123!",
        )
        login_response = self.client.post(
            self.login_url,
            {"mobile_number": user.mobile_number, "password": "StrongPass123!"},
            format="json",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")
        response = self.client.get(self.current_user_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["mobile_number"], user.mobile_number)
        self.assertEqual(response.data["name"], user.name)

    def test_logout_blacklists_refresh_token(self) -> None:
        user = User.objects.create_user(
            mobile_number="+14155550105",
            name="Evan Roe",
            password="StrongPass123!",
        )
        login_response = self.client.post(
            self.login_url,
            {"mobile_number": user.mobile_number, "password": "StrongPass123!"},
            format="json",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")
        logout_response = self.client.post(
            self.logout_url,
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)

        # The blacklisted refresh token should no longer be usable.
        refresh_response = self.client.post(
            self.refresh_url,
            {"refresh": login_response.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_activates_pending_invite_user(self) -> None:
        invited_user = User.objects.create_user(
            mobile_number="+14155550106",
            name="Pending Invite",
            password=None,
            is_active=False,
        )

        response = self.client.post(
            self.register_url,
            {
                "mobile_number": invited_user.mobile_number,
                "name": "Invited User",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invited_user.refresh_from_db()
        self.assertTrue(invited_user.is_active)
        self.assertEqual(invited_user.name, "Invited User")
        self.assertTrue(invited_user.has_usable_password())
