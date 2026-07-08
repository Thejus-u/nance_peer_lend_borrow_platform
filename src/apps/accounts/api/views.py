from __future__ import annotations

from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenViewBase

from apps.accounts.api.permissions import IsAuthenticatedAndActive
from apps.accounts.api.serializers import (
    ConnectGmailSerializer,
    CurrentUserSerializer,
    GmailAccountSerializer,
    LoginSerializer,
    LogoutSerializer,
    RefreshGmailTokenSerializer,
    RefreshTokenSerializer,
    RegisterSerializer,
    SyncGmailEmailsSerializer,
)
from apps.accounts.models import GmailAccount
from apps.accounts.services.auth_service import blacklist_refresh_token


class RegisterAPIView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class LoginAPIView(TokenViewBase):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]


class RefreshTokenAPIView(TokenViewBase):
    serializer_class = RefreshTokenSerializer
    permission_classes = [AllowAny]


class CurrentUserAPIView(generics.RetrieveAPIView):
    serializer_class = CurrentUserSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_object(self):
        return self.request.user


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            blacklist_refresh_token(refresh_token=serializer.validated_data["refresh"])
        except TokenError:
            return Response(
                {"detail": "Refresh token is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class GmailAccountListAPIView(generics.ListAPIView):
    serializer_class = GmailAccountSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        return GmailAccount.objects.filter(user=self.request.user)


class ConnectGmailAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = ConnectGmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.save(user=request.user)
        return Response(GmailAccountSerializer(account).data, status=status.HTTP_201_CREATED)


class RefreshGmailTokenAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = RefreshGmailTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.save(user=request.user)
        return Response(GmailAccountSerializer(account).data, status=status.HTTP_200_OK)


class SyncGmailEmailsAPIView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = SyncGmailEmailsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save(user=request.user)
        return Response(payload, status=status.HTTP_200_OK)
