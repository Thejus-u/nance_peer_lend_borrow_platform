from datetime import timedelta
from pathlib import Path
from typing import Any

import environ
from celery.schedules import crontab

# Root directory points to the repository root.
ROOT_DIR = Path(__file__).resolve().parents[3]
APPS_DIR = ROOT_DIR / "src"

env = environ.Env()
environ.Env.read_env(ROOT_DIR / ".env")

DJANGO_ENV = env("DJANGO_ENV", default="local")

SECRET_KEY = env("SECRET_KEY", default="unsafe-secret-key-change-me")
DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
	"django.contrib.admin",
	"django.contrib.auth",
	"django.contrib.contenttypes",
	"django.contrib.sessions",
	"django.contrib.messages",
	"django.contrib.staticfiles",
	"django.contrib.humanize",
	"channels",
	"corsheaders",
	"rest_framework",
	"rest_framework_simplejwt.token_blacklist",
	"apps.common",
	"apps.accounts",
	"apps.marketplace",
	"apps.loans",
	"apps.payments",
	"apps.notifications",
	"apps.communications",
	"apps.risk",
	"apps.compliance",
	"apps.audit",
	"apps.integrations",
	"apps.family",
]

MIDDLEWARE = [
	"django.middleware.security.SecurityMiddleware",
	"corsheaders.middleware.CorsMiddleware",
	"django.contrib.sessions.middleware.SessionMiddleware",
	"django.middleware.common.CommonMiddleware",
	"django.middleware.csrf.CsrfViewMiddleware",
	"django.contrib.auth.middleware.AuthenticationMiddleware",
	"django.contrib.messages.middleware.MessageMiddleware",
	"django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
	{
		"BACKEND": "django.template.backends.django.DjangoTemplates",
		"DIRS": [APPS_DIR / "templates"],
		"APP_DIRS": True,
		"OPTIONS": {
			"context_processors": [
				"django.template.context_processors.debug",
				"django.template.context_processors.request",
				"django.contrib.auth.context_processors.auth",
				"django.contrib.messages.context_processors.messages",
			],
		},
	},
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES: dict[str, dict[str, Any]] = {
	"default": env.db(
		"DATABASE_URL",
		default="postgres://peer_user:peer_pass@localhost:5432/peer_platform",
	)
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

CACHES = {
	"default": {
		"BACKEND": "django.core.cache.backends.redis.RedisCache",
		"LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
	}
}

PASSWORD_HASHERS = [
	"django.contrib.auth.hashers.Argon2PasswordHasher",
	"django.contrib.auth.hashers.PBKDF2PasswordHasher",
	"django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
	"django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
	{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
	{"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
	{"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
	{"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = ROOT_DIR / "staticfiles"
STATICFILES_DIRS = [ROOT_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = ROOT_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
	"DEFAULT_AUTHENTICATION_CLASSES": (
		"rest_framework_simplejwt.authentication.JWTAuthentication",
	),
	"DEFAULT_PERMISSION_CLASSES": (
		"rest_framework.permissions.IsAuthenticated",
	),
	"DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
	"PAGE_SIZE": 20,
	"DEFAULT_RENDERER_CLASSES": (
		"rest_framework.renderers.JSONRenderer",
	),
	"DEFAULT_PARSER_CLASSES": (
		"rest_framework.parsers.JSONParser",
	),
	"DEFAULT_THROTTLE_CLASSES": (
		"rest_framework.throttling.AnonRateThrottle",
		"rest_framework.throttling.UserRateThrottle",
	),
	"DEFAULT_THROTTLE_RATES": {
		"anon": env("DRF_THROTTLE_ANON", default="60/minute"),
		"user": env("DRF_THROTTLE_USER", default="120/minute"),
	},
}

SIMPLE_JWT = {
	"ACCESS_TOKEN_LIFETIME": timedelta(
		minutes=env.int("ACCESS_TOKEN_LIFETIME_MINUTES", default=15)
	),
	"REFRESH_TOKEN_LIFETIME": timedelta(
		days=env.int("REFRESH_TOKEN_LIFETIME_DAYS", default=7)
	),
	"ROTATE_REFRESH_TOKENS": True,
	"BLACKLIST_AFTER_ROTATION": True,
	"UPDATE_LAST_LOGIN": True,
	"ALGORITHM": "HS256",
	"SIGNING_KEY": SECRET_KEY,
	"AUTH_HEADER_TYPES": ("Bearer",),
	"AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_BEAT_SCHEDULE = {
	"notifications-dispatch-pending-every-minute": {
		"task": "notifications.dispatch_pending",
		"schedule": crontab(minute="*/1"),
		"args": (100,),
	},
	"loans-send-overdue-reminders-every-morning": {
		"task": "loans.send_overdue_reminders",
		"schedule": crontab(minute="0", hour="8"),
	},
}

CHANNEL_LAYERS = {
	"default": {
		"BACKEND": "channels_redis.core.RedisChannelLayer",
		"CONFIG": {
			"hosts": [REDIS_URL],
		},
	},
}

LOG_LEVEL = env("LOG_LEVEL", default="INFO")

GMAIL_CLIENT_ID = env("GMAIL_CLIENT_ID", default="")
GMAIL_CLIENT_SECRET = env("GMAIL_CLIENT_SECRET", default="")
GMAIL_TOKEN_URL = env("GMAIL_TOKEN_URL", default="https://oauth2.googleapis.com/token")
GMAIL_USERINFO_URL = env("GMAIL_USERINFO_URL", default="https://www.googleapis.com/oauth2/v3/userinfo")
GMAIL_MESSAGES_LIST_URL = env("GMAIL_MESSAGES_LIST_URL", default="https://gmail.googleapis.com/gmail/v1/users/me/messages")
GMAIL_MESSAGES_GET_URL = env("GMAIL_MESSAGES_GET_URL", default="https://gmail.googleapis.com/gmail/v1/users/me/messages")
GMAIL_BANK_SENDER_DOMAINS = env.list(
	"GMAIL_BANK_SENDER_DOMAINS",
	default=[
		"alerts.hdfcbank.com",
		"hdfcbank.net",
		"icicibank.com",
		"axisbank.com",
		"sbi.co.in",
		"kotak.com",
		"yesbank.in",
		"indusind.com",
		"rblbank.com",
	],
)

LOGGING = {
	"version": 1,
	"disable_existing_loggers": False,
	"formatters": {
		"verbose": {
			"format": "%(asctime)s %(levelname)s [%(name)s:%(lineno)d] %(message)s",
		},
		"simple": {
			"format": "%(levelname)s %(message)s",
		},
	},
	"handlers": {
		"console": {
			"class": "logging.StreamHandler",
			"formatter": "verbose",
		},
	},
	"root": {
		"handlers": ["console"],
		"level": LOG_LEVEL,
	},
	"loggers": {
		"django.db.backends": {
			"handlers": ["console"],
			"level": "WARNING",
			"propagate": False,
		},
		"celery": {
			"handlers": ["console"],
			"level": LOG_LEVEL,
			"propagate": False,
		},
	},
}
