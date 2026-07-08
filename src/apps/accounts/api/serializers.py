from __future__ import annotations

from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import GmailAccount, User
from apps.accounts.services.auth_service import register_user
from apps.accounts.services.gmail_oauth_service import (
    GmailOAuthService,
    InvalidGmailOAuthOperationError,
)


class CurrentUserSerializer(serializers.ModelSerializer):
    gmail_accounts = serializers.SlugRelatedField(
        slug_field="gmail_address",
        many=True,
        read_only=True,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "mobile_number",
            "name",
            "profile_image",
            "gmail_accounts",
            "date_joined",
        )


class RegisterSerializer(serializers.Serializer):
    mobile_number = serializers.CharField(max_length=16)
    name = serializers.CharField(max_length=255)
    password = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})
    password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )
    profile_image = serializers.ImageField(required=False, allow_null=True)
    gmail_address = serializers.EmailField(required=False, allow_null=True)

    def validate_mobile_number(self, value: str) -> str:
        existing_user = User.objects.filter(mobile_number=value).first()
        if existing_user and (existing_user.is_active or existing_user.has_usable_password()):
            raise serializers.ValidationError("A user with this mobile number already exists.")
        return value

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data: dict[str, object]) -> User:
        validated_data.pop("password_confirm")

        user = register_user(
            mobile_number=validated_data["mobile_number"],
            name=validated_data["name"],
            password=validated_data["password"],
            gmail_address=validated_data.get("gmail_address"),
            profile_image=validated_data.get("profile_image"),
        )
        return user


class LoginSerializer(TokenObtainPairSerializer):
    """Token pair serializer using mobile number credentials."""

    username_field = User.USERNAME_FIELD

    def validate(self, attrs: dict[str, str]) -> dict[str, object]:
        mobile_number = attrs.get("mobile_number")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            mobile_number=mobile_number,
            password=password,
        )

        if not user:
            raise serializers.ValidationError("Invalid mobile number or password.")

        if not user.is_active:
            raise serializers.ValidationError("User account is inactive.")

        refresh = self.get_token(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": CurrentUserSerializer(user).data,
        }


class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        try:
            refresh = RefreshToken(attrs["refresh"])
            attrs["access"] = str(refresh.access_token)
            return attrs
        except TokenError as exc:
            raise serializers.ValidationError({"refresh": "Token is invalid or expired."}) from exc


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class GmailAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = GmailAccount
        fields = (
            "id",
            "gmail_address",
            "is_primary",
            "is_verified",
            "token_expires_at",
            "last_synced_at",
            "created_at",
        )
        read_only_fields = fields


class ConnectGmailSerializer(serializers.Serializer):
    authorization_code = serializers.CharField(max_length=2048)
    redirect_uri = serializers.URLField(max_length=1000)
    set_primary = serializers.BooleanField(default=False)

    def save(self, *, user: User) -> GmailAccount:
        try:
            return GmailOAuthService.connect_gmail(
                user=user,
                authorization_code=self.validated_data["authorization_code"],
                redirect_uri=self.validated_data["redirect_uri"],
                set_primary=self.validated_data["set_primary"],
            )
        except InvalidGmailOAuthOperationError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class RefreshGmailTokenSerializer(serializers.Serializer):
    gmail_account_id = serializers.IntegerField(min_value=1)

    def save(self, *, user: User) -> GmailAccount:
        try:
            return GmailOAuthService.refresh_token(
                user=user,
                gmail_account_id=self.validated_data["gmail_account_id"],
            )
        except (InvalidGmailOAuthOperationError, GmailAccount.DoesNotExist) as exc:
            raise serializers.ValidationError({"detail": "Unable to refresh Gmail token."}) from exc


class SyncGmailEmailsSerializer(serializers.Serializer):
    gmail_account_id = serializers.IntegerField(min_value=1)
    max_results = serializers.IntegerField(min_value=1, max_value=200, default=20)
    query = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def save(self, *, user: User) -> dict[str, int]:
        try:
            result = GmailOAuthService.sync_emails(
                user=user,
                gmail_account_id=self.validated_data["gmail_account_id"],
                max_results=self.validated_data["max_results"],
                query=self.validated_data.get("query") or None,
            )
        except (InvalidGmailOAuthOperationError, GmailAccount.DoesNotExist) as exc:
            raise serializers.ValidationError({"detail": "Unable to sync Gmail emails."}) from exc
        return result
