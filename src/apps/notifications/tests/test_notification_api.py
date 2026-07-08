from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.notifications.models import Notification


class NotificationAPITestCase(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            mobile_number="+14151110011",
            name="Notification API User",
            password="StrongPass123!",
        )

        login = self.client.post(
            reverse("accounts:login"),
            {"mobile_number": self.user.mobile_number, "password": "StrongPass123!"},
            format="json",
        )
        self.access_token = login.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_notification_detail_returns_owned_notification(self) -> None:
        notification = Notification.objects.create(
            user=self.user,
            channel="in_app",
            title="Detail",
            message="Detail message",
            notification_type="general",
        )

        response = self.client.get(reverse("notifications:detail", kwargs={"pk": notification.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], notification.id)
        self.assertEqual(response.data["recipient"], self.user.id)

    def test_notification_create_sets_default_read_and_type(self) -> None:
        response = self.client.post(
            reverse("notifications:create"),
            {
                "channel": "in_app",
                "title": "Created",
                "message": "Created message",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["notification_type"], "general")
        self.assertEqual(response.data["is_read"], False)
