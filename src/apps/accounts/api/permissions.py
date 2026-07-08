from rest_framework.permissions import BasePermission


class IsAuthenticatedAndActive(BasePermission):
    """Allow access only to authenticated and active users."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)
