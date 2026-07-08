from rest_framework.permissions import BasePermission


class IsAuthenticatedAndActive(BasePermission):
    """Allow access only to authenticated and active users."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class IsLoanParticipantOrStaff(BasePermission):
    """Allow access to borrower, lender, or staff users."""

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        return bool(user.is_staff or obj.borrower_id == user.id or obj.lender_id == user.id)
