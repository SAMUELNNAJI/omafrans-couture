import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "Set DJANGO_SECRET_KEY to a long, unique secret before deploying."
        )
    SECRET_KEY = "local-development-only-key-not-for-production-omafrans-couture"

# Build ALLOWED_HOSTS from env var, always include Render's auto-generated host
_raw_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]

# Render sets RENDER_EXTERNAL_HOSTNAME automatically
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if _render_host and _render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_host)

# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "site_app.apps.SiteAppConfig",
    "auth_app.apps.AuthAppConfig",
    "dashboard_app.apps.DashboardAppConfig",
]

# ---------------------------------------------------------------------------
# Middleware  (WhiteNoise right after SecurityMiddleware)
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",   # ← serves static files
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "omafrans_config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "site_app.context_processors.site_contact",
            ],
        },
    },
]

WSGI_APPLICATION = "omafrans_config.wsgi.application"
ASGI_APPLICATION = "omafrans_config.asgi.application"

# ---------------------------------------------------------------------------
# Database  — Postgres on Render, SQLite locally
# ---------------------------------------------------------------------------
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    DATABASES = {"default": dj_database_url.parse(_db_url, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL             = "auth:login"
LOGIN_REDIRECT_URL    = "dashboard:index"
LOGOUT_REDIRECT_URL   = "site:home"

# ---------------------------------------------------------------------------
# i18n / tz
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE     = "Africa/Lagos"
USE_I18N      = True
USE_TZ        = True

# ---------------------------------------------------------------------------
# Static & Media
# ---------------------------------------------------------------------------
STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# WhiteNoise: compressed + immutable-cache for hashed files
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_ALL_ORIGINS = DEBUG   # relax only in dev

# ---------------------------------------------------------------------------
# Production hardening  (applied when DEBUG=False)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT             = True
    SESSION_COOKIE_SECURE           = True
    CSRF_COOKIE_SECURE              = True
    SECURE_HSTS_SECONDS             = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS  = True
    SECURE_HSTS_PRELOAD             = True
    SECURE_PROXY_SSL_HEADER         = ("HTTP_X_FORWARDED_PROTO", "https")
    # Render terminates SSL at the edge; trust its forwarded proto header
