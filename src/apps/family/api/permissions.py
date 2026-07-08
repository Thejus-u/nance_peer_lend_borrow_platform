from rest_framework.permissions import BasePermission


class IsFamilyAuthenticatedAndActive(BasePermission):
    """Allow family APIs only for authenticated and active users."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)
