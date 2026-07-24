"""Minimal Django settings for DRF endpoint parity."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-hls-cookie-proxy")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if host.strip()]
ROOT_URLCONF = "django_config.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

INSTALLED_APPS = [
    "rest_framework",
    "proxy_api",
]

MIDDLEWARE = []

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {},
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
COOKIE_STORE_BACKEND = os.environ.get("COOKIE_STORE_BACKEND", "json")
COOKIE_BASE_TTL_SECONDS = int(os.environ.get("COOKIE_BASE_TTL_SECONDS", "3600"))
COOKIE_CAMERA_TTL_SECONDS = int(os.environ.get("COOKIE_CAMERA_TTL_SECONDS", "300"))
COOKIE_REFRESH_LOCK_TTL_SECONDS = int(os.environ.get("COOKIE_REFRESH_LOCK_TTL_SECONDS", "120"))
REFRESH_WAIT_TIMEOUT_SECONDS = float(os.environ.get("REFRESH_WAIT_TIMEOUT_SECONDS", "5"))

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "0") == "1"
CELERY_TASK_EAGER_PROPAGATES = True

