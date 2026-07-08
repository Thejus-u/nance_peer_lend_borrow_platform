import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

# Initialize Django first so app registry is ready before importing project code
# that may depend on models/auth internals.
django_asgi_app = get_asgi_application()

from apps.loans.websocket_auth import JWTAuthMiddleware  # noqa: E402
from config.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": ASGIStaticFilesHandler(django_asgi_app),
        "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
