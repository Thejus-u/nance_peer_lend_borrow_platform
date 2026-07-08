from __future__ import annotations

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase


class HealthCheckAPITestCase(APITestCase):
    def test_health_endpoint_returns_healthy_payload(self) -> None:
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "healthy")
        self.assertEqual(response.data["application"], "up")
        self.assertEqual(response.data["database"], "connected")
        self.assertIn("redis", response.data)
        self.assertIn("timestamp", response.data)

    @patch("apps.common.api.views.HealthCheckAPIView._check_database", return_value=False)
    def test_health_endpoint_returns_unhealthy_when_database_fails(self, _mock_db) -> None:
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "unhealthy")
        self.assertEqual(response.data["database"], "disconnected")

    @patch("apps.common.api.views.HealthCheckAPIView._is_redis_configured", return_value=True)
    @patch("apps.common.api.views.HealthCheckAPIView._check_redis", return_value=False)
    def test_health_endpoint_returns_unhealthy_when_redis_fails(self, _mock_redis, _mock_configured) -> None:
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "unhealthy")
        self.assertEqual(response.data["redis"], "disconnected")