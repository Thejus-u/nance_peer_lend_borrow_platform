from __future__ import annotations

from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsAuthenticatedAndActive
from apps.payments.api.serializers import (
    AccountStatusActionSerializer,
    DiscoverAccountSerializer,
    DiscoveredAccountSerializer,
)
from apps.payments.models import DiscoveredAccount
from apps.payments.models import DiscoveredAccountStatus


class DiscoveredAccountListAPIView(generics.ListAPIView):
    serializer_class = DiscoveredAccountSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        status_filter = self.request.query_params.get("status")
        valid_statuses = {choice for choice, _ in DiscoveredAccountStatus.choices}
        if status_filter in valid_statuses:
            return DiscoveredAccount.objects.filter(user=self.request.user, status=status_filter)
        return DiscoveredAccount.objects.filter(
            user=self.request.user,
            status=DiscoveredAccountStatus.UNLINKED,
        )


class DiscoverAccountAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = DiscoverAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        discovered = serializer.save(user_id=request.user.id)
        return Response(DiscoveredAccountSerializer(discovered).data, status=status.HTTP_201_CREATED)


class DiscoveredAccountStatusAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, account_id: int, action: str, *args, **kwargs) -> Response:
        serializer = AccountStatusActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        discovered = serializer.save(account_id=account_id, user_id=request.user.id, action=action)
        return Response(DiscoveredAccountSerializer(discovered).data, status=status.HTTP_200_OK)
