"""
Django settings for KPL Auction Engine.

Local:  DEBUG=True, SQLite, console logging
Render: set RENDER=true env var → DEBUG=False, WhiteNoise, allowed hosts
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ────────────────────────────────────────────────
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-kpl-local-dev-key-change-in-production"
)

IS_RENDER = os.environ.get("RENDER", "false").lower() == "true"
DEBUG     = not IS_RENDER

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
if IS_RENDER:
    render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
    if render_host:
        ALLOWED_HOSTS.append(render_host)

CSRF_TRUSTED_ORIGINS = []
if IS_RENDER:
    render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
    if render_host:
        CSRF_TRUSTED_ORIGINS.append(f"https://{render_host}")

# ── Apps ────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "auction",
]

# ── Middleware ──────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]
if IS_RENDER:
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")

MIDDLEWARE += [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "auction.context_processors.tournament_settings",
        ]
    },
}]

WSGI_APPLICATION = "config.wsgi.application"

# ── Database ────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME":   BASE_DIR / "db.sqlite3",
    }
}

# ── Static files ────────────────────────────────────────────
STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

if IS_RENDER:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ── Media files ─────────────────────────────────────────────
MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── Auth ────────────────────────────────────────────────────
LOGIN_URL = "/admin/login/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
