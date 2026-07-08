from __future__ import annotations

from django.http import HttpResponseRedirect
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsAuthenticatedAndActive
from apps.integrations.api.serializers import (
    GmailConnectSerializer,
    GmailMessageSerializer,
    GmailStatusSerializer,
    GmailStatusResponseSerializer,
    GmailSyncSerializer,
)
from apps.integrations.selectors import GmailSelector
from apps.integrations.services.gmail_oauth import GmailOAuthError, GmailOAuthService


class GmailConnectAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request: Request, *args, **kwargs) -> Response:
        serializer = GmailConnectSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        oauth_url = serializer.build_oauth_url(user_id=request.user.id)
        return Response({"oauth_url": oauth_url}, status=status.HTTP_200_OK)


class GmailCallbackAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, *args, **kwargs) -> Response:
        authorization_code = request.query_params.get("code", "")
        state_token = request.query_params.get("state", "")
        if not authorization_code or not state_token:
            return Response({"detail": "Missing OAuth callback parameters."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            account, frontend_redirect = GmailOAuthService.connect_from_callback(
                authorization_code=authorization_code,
                state_token=state_token,
            )
        except GmailOAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if frontend_redirect:
            separator = "&" if "?" in frontend_redirect else "?"
            return HttpResponseRedirect(f"{frontend_redirect}{separator}gmail=connected&email={account.email}")

        return Response({"connected": True, "email": account.email}, status=status.HTTP_200_OK)


class GmailStatusAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request: Request, *args, **kwargs) -> Response:
        payload = GmailStatusResponseSerializer.from_user(user_id=request.user.id)
        serializer = GmailStatusSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GmailSyncAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = GmailSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save(user_id=request.user.id)
        return Response(payload, status=status.HTTP_200_OK)


class GmailMessageListAPIView(generics.ListAPIView):
    serializer_class = GmailMessageSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        return GmailSelector.list_messages(user_id=self.request.user.id)