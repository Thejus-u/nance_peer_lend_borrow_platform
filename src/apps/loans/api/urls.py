from django.urls import path

from apps.loans.api.views import (
    ActiveLoansListAPIView,
    IncomingLoanRequestListAPIView,
    LoanAcceptAPIView,
    LoansBorrowedListAPIView,
    LoanCancelAPIView,
    LoanCreateAPIView,
    LoansLentListAPIView,
    LoanListAPIView,
    LoanDetailAPIView,
    LoanRejectAPIView,
    RepaymentCreateAPIView,
    RepaymentPayAPIView,
    SettledLoansListAPIView,
)

app_name = "loans"

urlpatterns = [
    path("", LoanCreateAPIView.as_view(), name="create"),
    path("list/", LoanListAPIView.as_view(), name="list"),
    path("incoming/", IncomingLoanRequestListAPIView.as_view(), name="incoming"),
    path("lent/", LoansLentListAPIView.as_view(), name="lent"),
    path("borrowed/", LoansBorrowedListAPIView.as_view(), name="borrowed"),
    path("active/", ActiveLoansListAPIView.as_view(), name="active"),
    path("settled/", SettledLoansListAPIView.as_view(), name="settled"),
    path("<int:pk>/", LoanDetailAPIView.as_view(), name="detail"),
    path("<int:loan_id>/accept/", LoanAcceptAPIView.as_view(), name="accept"),
    path("<int:loan_id>/reject/", LoanRejectAPIView.as_view(), name="reject"),
    path("<int:loan_id>/cancel/", LoanCancelAPIView.as_view(), name="cancel"),
    path("<int:loan_id>/repayments/", RepaymentCreateAPIView.as_view(), name="repayment_create"),
    path("repayments/<int:repayment_id>/pay/", RepaymentPayAPIView.as_view(), name="repayment_pay"),
]