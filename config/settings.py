"""Skillbridge settings — one file, one project, one database.

Everything the application needs is either in the Python standard library or in
Django. There is no cache server, message broker, worker, search engine, object
store or frontend build step, so there is nothing to configure for them and
nothing to install before:

 python manage.py migrate
 python manage.py runserver
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if it exists
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    with open(_env_file, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

# Local development key. Generate a fresh one before deploying anywhere real:
# python -c "import secrets; print(secrets.token_urlsafe(50))"
SECRET_KEY = "django-insecure-local-development-only-change-before-deploying"

DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:8000", "http://localhost:8000"]


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
DJANGO_APPS = [
    "apps.core.admin_config.SkillbridgeAdminConfig",  # django.contrib.admin, branded
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

SKILLBRIDGE_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.profiles",
    "apps.portfolios",
    "apps.wallets",
]

INSTALLED_APPS = DJANGO_APPS + SKILLBRIDGE_APPS


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Skillbridge: remembers who is acting (for the audit trail), and turns a
    # DomainError raised deep in a service into a proper response.
    "apps.core.middleware.RequestActorMiddleware",
    "apps.core.middleware.DomainErrorMiddleware",
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
                "apps.core.context_processors.site",
                "apps.wallets.context_processors.wallet",
            ],
            "builtins": [
                "apps.core.templatetags.skillbridge",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --------------------------------------------------------------------------- #
# Database — SQLite, created by `migrate`, no server to install
# --------------------------------------------------------------------------- #
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            # SQLite serialises writers. Without a timeout, a second writer
            # arriving mid-transaction fails instantly with "database is
            # locked" instead of waiting its turn. Write-ahead logging and
            # foreign-key enforcement are switched on in
            # apps/core/apps.py, which works on every Django 5 release.
            "timeout": 20,
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

# Sign-in accepts either the email address or the username, and refuses a
# suspended account before it ever gets a session.
#
# Deliberately the only backend. Leaving Django's ModelBackend as a fallback
# would undo that: it authenticates on `is_active` alone, so a suspended
# account refused by the first backend would simply be let in by the second.
AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.EmailOrUsernameBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"


# --------------------------------------------------------------------------- #
# Internationalisation
# --------------------------------------------------------------------------- #
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True


# --------------------------------------------------------------------------- #
# Static and media
# --------------------------------------------------------------------------- #
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Private project files are served by apps.files.views.serve_file, which checks
# permission first. MEDIA_URL only ever serves deliberately public images.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024


# --------------------------------------------------------------------------- #
# Email — SMTP backend for sending real emails, with console fallback
# --------------------------------------------------------------------------- #
_smtp_user = os.getenv("EMAIL_HOST_USER", "").strip()
_default_backend = (
    "django.core.mail.backends.smtp.EmailBackend"
    if _smtp_user and _smtp_user != "your_email@gmail.com"
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", _default_backend)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in ("true", "1", "yes")
EMAIL_HOST_USER = _smtp_user
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    f"SkillBridge <{_smtp_user or 'noreply@skillbridge.local'}>",
)
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000")

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # read by static/js/csrf.js for fetch POSTs
X_FRAME_OPTIONS = "DENY"


# --------------------------------------------------------------------------- #
# Business rules — every number the specification fixes lives here, so changing
# one is a deliberate edit in a single place rather than a hunt through code.
# --------------------------------------------------------------------------- #
SKILLCOIN = {
    "CODE": "SKC",
    "SYMBOL": "৳",
    "NAME": "SkillCoin",
    "BDT_RATE": 1,  # 1 SkillCoin = 1 BDT
    "DECIMAL_PLACES": 2,
}

BUSINESS_RULES = {
    # The platform's central promise: after a submission the client has this
    # long to approve, revise or dispute. Silence pays the freelancer.
    "TASK_REVIEW_WINDOW_HOURS": 48,
    "PROJECT_REVIEW_WINDOW_HOURS": 48,
    "OFFER_EXPIRY_HOURS": 72,
    "TEAM_INVITE_EXPIRY_HOURS": 168,
    "EMAIL_TOKEN_EXPIRY_HOURS": 48,
    "MIN_DEPOSIT": 100,
    "MIN_WITHDRAWAL": 500,
    "MIN_JOB_BUDGET": 500,
    "MAX_PORTFOLIO_REFERENCES": 5,
    "DEFAULT_REVISION_LIMIT": 2,
    "MAX_UPLOAD_MB": 25,
    "PAGE_SIZE": 20,
}

# What may be uploaded. Checked by extension and by size; anything not listed
# is refused before it ever reaches MEDIA_ROOT.
ALLOWED_UPLOAD_EXTENSIONS = [
    "pdf",
    "doc",
    "docx",
    "odt",
    "rtf",
    "txt",
    "md",
    "csv",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "svg",
    "zip",
    "tar",
    "gz",
    "json",
    "xml",
    "psd",
    "fig",
    "sketch",
]

# The numbers a user is told to send money to, and that payouts come from.
# Manual records only: there is no payment gateway.
PAYMENT_CHANNELS = {
    "BKASH": {"label": "bKash", "number": "01700000000", "type": "Merchant"},
    "NAGAD": {"label": "Nagad", "number": "01800000000", "type": "Merchant"},
}

# The assistant answers from a permission-checked context document using a
# local rule-based renderer. An external provider may be plugged in later; the
# site must never require one.
AI = {
    "ENABLED": True,
    "PROVIDER": None,
}
