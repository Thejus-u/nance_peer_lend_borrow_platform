from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        database_connected = self._check_database()
        redis_configured = self._is_redis_configured()
        redis_connected = self._check_redis() if redis_configured else None

        is_healthy = database_connected and (redis_connected is not False)
        status_code = 200 if is_healthy else 503

        payload = {
            "status": "healthy" if is_healthy else "unhealthy",
            "application": "up",
            "database": "connected" if database_connected else "disconnected",
            "redis": (
                "connected"
                if redis_connected is True
                else "disconnected"
                if redis_connected is False
                else "not_configured"
            ),
            "timestamp": timezone.now().isoformat(),
        }

        return Response(payload, status=status_code)

    @staticmethod
    def _check_database() -> bool:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Exception:
            return False

    @staticmethod
    def _is_redis_configured() -> bool:
        backend = str(settings.CACHES.get("default", {}).get("BACKEND", ""))
        return "RedisCache" in backend

    @staticmethod
    def _check_redis() -> bool:
        try:
            cache.set("healthcheck", "ok", timeout=5)
            return cache.get("healthcheck") == "ok"
        except Exception:
            return False


class DBTestAPIView(APIView):
    """
    Temporary endpoint to verify PostgreSQL connectivity from ECS.
    Remove after debugging.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT NOW();")
                row = cursor.fetchone()

            return Response(
                {
                    "status": "success",
                    "message": "Database connection successful",
                    "database_time": str(row[0]),
                },
                status=200,
            )
        except Exception as exc:
            return Response(
                {
                    "status": "error",
                    "message": str(exc),
                },
                status=500,
            )