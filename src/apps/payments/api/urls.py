from django.urls import path

from apps.payments.api.views import (
    DiscoverAccountAPIView,
    DiscoveredAccountListAPIView,
    DiscoveredAccountStatusAPIView,
)
from apps.payments.api.transaction_views import (
    BankTransactionCreateAPIView,
    BankTransactionListAPIView,
    BankTransactionSummaryAPIView,
)

app_name = "payments"

urlpatterns = [
    path("transactions/", BankTransactionListAPIView.as_view(), name="transactions"),
    path("transactions/create/", BankTransactionCreateAPIView.as_view(), name="transactions_create"),
    path("transactions/summary/", BankTransactionSummaryAPIView.as_view(), name="transactions_summary"),
    path("discovered-accounts/", DiscoveredAccountListAPIView.as_view(), name="discovered_accounts"),
    path("discovered-accounts/discover/", DiscoverAccountAPIView.as_view(), name="discover_account"),
    path(
        "discovered-accounts/<int:account_id>/<str:action>/",
        DiscoveredAccountStatusAPIView.as_view(),
        name="discovered_account_action",
    ),
]