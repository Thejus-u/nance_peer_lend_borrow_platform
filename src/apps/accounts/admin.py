from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import GmailAccount, GmailSyncedEmail, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("id",)
    list_display = ("id", "mobile_number", "name", "is_active", "is_staff", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("mobile_number", "name")

    fieldsets = (
        (None, {"fields": ("mobile_number", "password")}),
        ("Personal Info", {"fields": ("name", "profile_image")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important Dates", {"fields": ("last_login", "date_joined", "updated_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("mobile_number", "name", "password1", "password2", "is_staff", "is_active"),
            },
        ),
    )

    readonly_fields = ("date_joined", "updated_at", "last_login")


@admin.register(GmailAccount)
class GmailAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "gmail_address",
        "user",
        "is_primary",
        "is_verified",
        "last_synced_at",
        "created_at",
    )
    list_filter = ("is_primary", "is_verified", "created_at")
    search_fields = ("gmail_address", "user__mobile_number", "user__name")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at", "last_synced_at")


@admin.register(GmailSyncedEmail)
class GmailSyncedEmailAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "gmail_account",
        "gmail_message_id",
        "sender_email",
        "subject",
        "received_at",
        "synced_at",
    )
    search_fields = (
        "gmail_message_id",
        "gmail_account__gmail_address",
        "subject",
        "sender_email",
    )
    list_filter = ("received_at", "synced_at")
    autocomplete_fields = ("gmail_account",)
    readonly_fields = ("synced_at",)
