from django.urls import path

from apps.loans.consumers import LoanEventsConsumer

websocket_urlpatterns = [
    path("ws/loans/", LoanEventsConsumer.as_asgi(), name="ws_loans_events"),
]
