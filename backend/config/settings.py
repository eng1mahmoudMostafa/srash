"""
DJANGO settings for the anonymous-messages platform (صراحة).

Sensitive values are read from environment variables. See repo root `.env.example`.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# Harden: never run with the development placeholder in production.
if not DEBUG and SECRET_KEY == "dev-only-change-me":
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be set to a strong random value in production."
    )

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.onrender.com"
    ).split(",")
    if h.strip()
]

# Render.com injects the public URL of the service automatically, so the
# production deploy works with zero host configuration.
_RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
if _RENDER_EXTERNAL_URL:
    _host = _RENDER_EXTERNAL_URL.split("://", 1)[-1]
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "corsheaders",
    "django_filters",
    # Local
    "users",
    "messages_app",
    "moderation",
    "notifications",
    "common",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "common.middleware.LastSeenMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Full-URL support (Render/Heroku style): postgres://user:pass@host:port/name
if os.environ.get("DATABASE_URL") and not os.environ.get("DB_HOST"):
    from urllib.parse import urlparse

    _u = urlparse(os.environ["DATABASE_URL"])
    os.environ.setdefault("DB_ENGINE", "postgres")
    os.environ.setdefault("DB_NAME", _u.path.lstrip("/"))
    os.environ.setdefault("DB_USER", _u.username or "")
    os.environ.setdefault("DB_PASSWORD", _u.password or "")
    os.environ.setdefault("DB_HOST", _u.hostname or "")
    os.environ.setdefault("DB_PORT", str(_u.port or "5432"))

if os.environ.get("DB_ENGINE", "postgres") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "anonymous_app"),
            "USER": os.environ.get("DB_USER", "app"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "app"),
            "HOST": os.environ.get("DB_HOST", "db"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "ar"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Built React app served from the same origin (for the public tunnel / prod).
FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"
STATICFILES_DIRS = [
    FRONTEND_DIST_DIR / "assets" if (FRONTEND_DIST_DIR / "assets").exists() else FRONTEND_DIST_DIR,
]
WHITENOISE_USE_FINDERS = True
WHITENOISE_INDEX_FILE = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Cache / rate limiting backend
# ---------------------------------------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
if os.environ.get("CACHE_BACKEND", "redis") == "redis":
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "default-snowflake",
        }
    }

# ---------------------------------------------------------------------------
# Sessions + HttpOnly cookies (SameSite=Lax, Secure when COOKIE_SECURE=1)
# ---------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_HTTPONLY = False  # JS reads the csrf token to send it with requests.
CSRF_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        # Wildcards keep POSTs working on Render and quick tunnels without
        # knowing the final subdomain in advance.
        "http://localhost:5173,http://localhost:8000,"
        "https://*.trycloudflare.com,https://*.onrender.com",
    ).split(",")
    if o.strip()
]
if _RENDER_EXTERNAL_URL and _RENDER_EXTERNAL_URL not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(_RENDER_EXTERNAL_URL)

# Release security checklist defaults.
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_SSL_REDIRECT = os.environ.get("COOKIE_SECURE", "0") == "1"
X_FRAME_OPTIONS = "DENY"

if os.environ.get("COOKIE_SECURE", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_BROWSER_XSS_FILTER = True
    # Block script/style/iframe injection via user-supplied content.
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# ---------------------------------------------------------------------------
# DRF throttles — a second layer of defense on top of the app-level limiter
# (protects login/register/CSRF endpoints from credential stuffing too).
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.environ.get("DRF_THROTTLE_ANON", "60/min"),
        "user": os.environ.get("DRF_THROTTLE_USER", "120/min"),
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# ---------------------------------------------------------------------------
# CORS for the React dev server
# ---------------------------------------------------------------------------
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:5173"
    ).split(",")
    if o.strip()
]

# ---------------------------------------------------------------------------
# Application-specific settings
# ---------------------------------------------------------------------------
# Secret used to build the per-IP HMAC for abuse/rate limiting.
# The raw IP is NEVER stored alongside a message.
IP_HMAC_KEY = os.environ.get("IP_HMAC_KEY", "dev-ip-hmac-key")

RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "5"))
RATE_LIMIT_PER_HOUR = int(os.environ.get("RATE_LIMIT_PER_HOUR", "20"))

MAX_MESSAGE_LENGTH = int(os.environ.get("MAX_MESSAGE_LENGTH", "10000"))

# Base64(AES-256-GCM key) used for field-level encryption.
MESSAGE_ENCRYPTION_KEY = os.environ.get(
    "MESSAGE_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
)

RETENTION_PURGE_DAYS = int(os.environ.get("RETENTION_PURGE_DAYS", "30"))

SITE_BASE_URL = (
    os.environ.get("SITE_BASE_URL") or _RENDER_EXTERNAL_URL or "http://localhost:8000"
)

# ---------------------------------------------------------------------------
# Media uploads (avatars) — served safely by the backend itself.
# ---------------------------------------------------------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Message image attachments: allow up to 5 MB uploads (Django's default
# 2.5 MB body cap would silently reject them with a 400).
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ---------------------------------------------------------------------------
# E-mail — console backend prints to the runserver log during development;
# switch to SMTP by setting EMAIL_BACKEND/EMAIL_HOST* in `.env`.
# ---------------------------------------------------------------------------
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "صراحة <no-reply@sraha.local>"
)
# If someone requests a real SMTP backend but leaves the account empty, fall
# back to the console (log-only) backend instead of failing every send
# silently — a fresh install must never silently swallow the notification.
if EMAIL_BACKEND.endswith("smtp.EmailBackend") and not (
    EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# Premium subscription (توثيق الحساب) — manual transfer approved by owner.
# Owner later sets real transfer details in `.env`: PAYMENT_INFO="..."
# ---------------------------------------------------------------------------
PREMIUM_PRICE_EGP = int(os.environ.get("PREMIUM_PRICE_EGP", "100"))
PREMIUM_DAYS = int(os.environ.get("PREMIUM_DAYS", "30"))
# Capacity limits for verified subscriptions (visible to users, decremented
# with every approved subscription — counted per Cairo calendar day/month).
SUB_SLOTS_DAY = int(os.environ.get("SUB_SLOTS_DAY", "600"))
SUB_SLOTS_MONTH = int(os.environ.get("SUB_SLOTS_MONTH", "2000"))
PAYMENT_INFO = os.environ.get(
    "PAYMENT_INFO",
    "حوّل 100 جنيه شهريًا على رقم فودافون كاش / إنستاباي: 01130278851 "
    "ثم أدخل رقم عملية التحويل في الحقل أدناه وسيقرر المشرف الطلب من لوحة الإدارة.",
)