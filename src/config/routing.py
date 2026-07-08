from django.urls import URLPattern

from apps.loans.routing import websocket_urlpatterns as loan_websocket_urlpatterns

websocket_urlpatterns: list[URLPattern] = [
	*loan_websocket_urlpatterns,
]
