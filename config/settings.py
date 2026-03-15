from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────────────────────
# Environment detection
# On Render, set env var:  RENDER=true
# Locally this is never set, so IS_RENDER = False automatically
# ─────────────────────────────────────────────────────────────
IS_RENDER = os.environ.get("RENDER", "false").lower() == "true"

# ─────────────────────────────────────────────────────────────
# Secret key
# Locally:  hardcoded dev key (fine for local use)
# Render:   set SECRET_KEY env var in dashboard
# ─────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-local-only")

# ─────────────────────────────────────────────────────────────
# Debug — True locally, False on Render
# ─────────────────────────────────────────────────────────────
DEBUG = not IS_RENDER

# ─────────────────────────────────────────────────────────────
# Allowed hosts
# ─────────────────────────────────────────────────────────────
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

if IS_RENDER:
    ALLOWED_HOSTS += [
        ".onrender.com",
        os.environ.get("RENDER_EXTERNAL_HOSTNAME", ""),
    ]

# ─────────────────────────────────────────────────────────────
# CSRF trusted origins — required for POST forms on HTTPS
# ─────────────────────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = []

if IS_RENDER:
    render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
    if render_host:
        CSRF_TRUSTED_ORIGINS.append(f"https://{render_host}")
    CSRF_TRUSTED_ORIGINS.append("https://*.onrender.com")

# ─────────────────────────────────────────────────────────────
# Installed apps
# ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "auction",
]

# ─────────────────────────────────────────────────────────────
# Middleware — WhiteNoise is harmless locally, required on Render
# ─────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "auction.context_processors.tournament_settings",
    ]},
}]

WSGI_APPLICATION = "config.wsgi.application"

# ─────────────────────────────────────────────────────────────
# Database
# Uses SQLite locally and on Render by default.
# If DATABASE_URL env var is set (e.g. Render Postgres add-on),
# dj_database_url picks it up automatically.
# ─────────────────────────────────────────────────────────────
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# ─────────────────────────────────────────────────────────────
# Static files
# STATICFILES_DIRS = your source files (both local and Render)
# STATIC_ROOT     = where collectstatic writes (Render only)
# WhiteNoise serves from STATIC_ROOT everywhere
# ─────────────────────────────────────────────────────────────
STATIC_URL       = "/static/"
STATIC_ROOT      = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ─────────────────────────────────────────────────────────────
# Media files (uploaded banners, player photos)
# ─────────────────────────────────────────────────────────────
MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ─────────────────────────────────────────────────────────────
# Misc
# ─────────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/admin/login/"
