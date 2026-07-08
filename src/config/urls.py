from django.contrib import admin
from django.urls import include, path

from apps.common.api.views import HealthCheckAPIView

from apps.common.api.views import (
    HealthCheckAPIView,
    DBTestAPIView,
)

urlpatterns = [
	path("", include("apps.common.api.frontend_urls")),
	path("health/", HealthCheckAPIView.as_view(), name="health"),
	path("admin/", admin.site.urls),
	path("api/v1/common/", include("apps.common.api.urls")),
	path("api/v1/accounts/", include("apps.accounts.api.urls")),
	path("api/v1/marketplace/", include("apps.marketplace.api.urls")),
	path("api/v1/loans/", include("apps.loans.api.urls")),
	path("api/v1/payments/", include("apps.payments.api.urls")),
	path("api/v1/communications/", include("apps.communications.api.urls")),
	path("api/v1/risk/", include("apps.risk.api.urls")),
	path("api/v1/compliance/", include("apps.compliance.api.urls")),
	path("api/v1/audit/", include("apps.audit.api.urls")),
	path("api/v1/integrations/", include("apps.integrations.api.urls")),
	path("api/v1/family/", include("apps.family.api.urls")),
    path("db-test/", DBTestAPIView.as_view(), name="db_test"),
	path("api/v1/notifications/", include("apps.notifications.api.urls")),
]
