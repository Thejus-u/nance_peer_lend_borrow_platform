from django.contrib import admin

from apps.loans.models import Loan, Repayment


class RepaymentInline(admin.TabularInline):
    model = Repayment
    extra = 0
    fields = (
        "installment_number",
        "due_date",
        "amount_due",
        "amount_paid",
        "status",
        "paid_at",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "public_id",
        "borrower",
        "lender",
        "status",
        "principal_amount",
        "currency",
        "interest_rate",
        "repayment_term_months",
        "created_at",
    )
    list_filter = ("status", "currency", "created_at")
    search_fields = (
        "public_id",
        "borrower__mobile_number",
        "borrower__name",
        "lender__mobile_number",
        "lender__name",
    )
    autocomplete_fields = ("borrower", "lender")
    readonly_fields = ("public_id", "created_at", "updated_at")
    inlines = (RepaymentInline,)


@admin.register(Repayment)
class RepaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "loan",
        "installment_number",
        "due_date",
        "amount_due",
        "amount_paid",
        "status",
        "paid_at",
    )
    list_filter = ("status", "due_date", "created_at")
    search_fields = ("loan__public_id", "loan__borrower__mobile_number", "loan__lender__mobile_number")
    autocomplete_fields = ("loan",)
    readonly_fields = ("created_at", "updated_at")
