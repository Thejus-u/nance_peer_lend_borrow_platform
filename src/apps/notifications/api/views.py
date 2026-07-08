from __future__ import annotations

from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsAuthenticatedAndActive
from apps.notifications.api.serializers import (
    NotificationCreateSerializer,
    NotificationFailSerializer,
    NotificationSerializer,
)
from apps.notifications.models import Notification
from apps.notifications.services.notification_service import NotificationService


class NotificationListAPIView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class NotificationDetailAPIView(generics.RetrieveAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class NotificationCreateAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = NotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notification = serializer.save(user_id=request.user.id)
        return Response(NotificationSerializer(notification).data, status=status.HTTP_201_CREATED)


class NotificationMarkSentAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, notification_id: int, *args, **kwargs) -> Response:
        notification = NotificationService.mark_sent(notification_id=notification_id)
        return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)


class NotificationMarkFailedAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, notification_id: int, *args, **kwargs) -> Response:
        serializer = NotificationFailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notification = serializer.save(notification_id=notification_id)
        return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)
