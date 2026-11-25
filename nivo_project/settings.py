
"""
Django settings for NIVO project.
CodeAlpha Full Stack Development Internship - Task 2
Platform: NIVO - Modern Social Media Platform
"""

import os
import sys
import importlib.util
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv


# =========================================================
# BASE CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in ("true", "1", "yes", "on")


def env_list(name, default=""):
    return [
        item.strip()
        for item in os.environ.get(name, default).split(",")
        if item.strip()
    ]


# =========================================================
# SECURITY
# =========================================================

SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()

if not SECRET_KEY:
    raise ImproperlyConfigured(
        "SECRET_KEY is missing. Set it in your local .env file."
    )

DEBUG = env_bool("DEBUG", False)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")

if not ALLOWED_HOSTS and DEBUG:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS must be configured when DEBUG=False."
    )

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

if not CSRF_TRUSTED_ORIGINS and DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

# Trust forwarded headers only when running behind a trusted proxy.
TRUST_PROXY_HEADERS = env_bool("TRUST_PROXY_HEADERS", False)

USE_X_FORWARDED_HOST = TRUST_PROXY_HEADERS

if TRUST_PROXY_HEADERS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)

SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Enable HSTS after confirming HTTPS works correctly in production.
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", False
)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)


# =========================================================
# APPLICATIONS
# =========================================================

INSTALLED_APPS = [
    "channels",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # NIVO Core Apps
    "accounts.apps.AccountsConfig",
    "posts.apps.PostsConfig",
    "notifications.apps.NotificationsConfig",
    "chat.apps.ChatConfig",
]


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# URLS AND TEMPLATES
# =========================================================

ROOT_URLCONF = "nivo_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "notifications.context_processors.unread_notifications_count",
                "chat.context_processors.unread_messages_count",
            ],
        },
    },
]

WSGI_APPLICATION = "nivo_project.wsgi.application"
ASGI_APPLICATION = "nivo_project.asgi.application"


# =========================================================
# CHANNEL LAYERS
# =========================================================

CHANNEL_LAYER_BACKEND = os.environ.get(
    "CHANNEL_LAYER_BACKEND", "memory"
).strip().lower()

# Tests always use the in-memory layer.
if "test" in sys.argv:
    CHANNEL_LAYER_BACKEND = "memory"

if CHANNEL_LAYER_BACKEND == "memory":
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

elif CHANNEL_LAYER_BACKEND == "redis":
    if importlib.util.find_spec("channels_redis") is None:
        raise ImproperlyConfigured(
            "Redis channel layer selected, but channels-redis is not installed. "
            "Install it with: py -m pip install channels-redis"
        )

    REDIS_URL = os.environ.get(
        "REDIS_URL", "redis://127.0.0.1:6379/0"
    ).strip()

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        }
    }

else:
    raise ImproperlyConfigured(
        "CHANNEL_LAYER_BACKEND must be either 'memory' or 'redis'."
    )


# =========================================================
# DATABASE
# =========================================================

USE_POSTGRES = env_bool("USE_POSTGRES", False)

if USE_POSTGRES:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "nivo_db"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# =========================================================
# PASSWORD VALIDATION
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# Faster password hashing during tests only.
if "test" in sys.argv:
    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]


# =========================================================
# INTERNATIONALIZATION
# =========================================================

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"

USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("en", _("English")),
    ("ar", _("العربية")),
]

LOCALE_PATHS = [
    BASE_DIR / "locale",
]


# =========================================================
# STATIC FILES
# =========================================================

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"


# =========================================================
# MEDIA FILES
# =========================================================

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# =========================================================
# AUTHENTICATION
# =========================================================

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "posts:feed"
LOGOUT_REDIRECT_URL = "accounts:login"


# =========================================================
# UPLOAD LIMITS
# =========================================================

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024


# =========================================================
# DEFAULTS
# =========================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
