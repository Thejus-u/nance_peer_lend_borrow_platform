from django.urls import path
from django.views.generic import TemplateView

app_name = "frontend"

urlpatterns = [
    path("app/login/", TemplateView.as_view(template_name="frontend/login.html"), name="login"),
    path("app/register/", TemplateView.as_view(template_name="frontend/register.html"), name="register"),
    path("app/dashboard/", TemplateView.as_view(template_name="frontend/dashboard.html"), name="dashboard"),
    path("app/create-loan/", TemplateView.as_view(template_name="frontend/create-loan.html"), name="create_loan"),
    path("app/loan-list/", TemplateView.as_view(template_name="frontend/loan-list.html"), name="loan_list"),
    path("app/loan-detail/", TemplateView.as_view(template_name="frontend/loan-detail.html"), name="loan_detail"),
    path("app/repayment/", TemplateView.as_view(template_name="frontend/repayment.html"), name="repayment"),
    path("app/family-ledger/", TemplateView.as_view(template_name="frontend/family-ledger.html"), name="family_ledger"),
    path("app/transactions/", TemplateView.as_view(template_name="frontend/transactions.html"), name="transactions"),
    path("app/discovered-accounts/", TemplateView.as_view(template_name="frontend/discovered-accounts.html"), name="discovered_accounts"),
    path("app/notifications/", TemplateView.as_view(template_name="frontend/notifications.html"), name="notifications"),
]
