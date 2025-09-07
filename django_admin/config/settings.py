"""
Django settings for config project (Django 5.2.x)

Особенности:
- БД: PostgreSQL (хост 94.241.142.172:8083, БД llm)
- RU/Мск локаль
- ALLOWED_HOSTS = ["*"] по запросу
- Логирование в консоль для отладки
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ────────────────────────────────────────────────────────────────────────────────
# БЕЗОПАСНОСТЬ / ОСНОВНЫЕ ПАРАМЕТРЫ
# ────────────────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]  # по вашему пожеланию

# --- безопасность за прокси/https (если есть nginx/traefik) ---
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # nginx должен прокидывать X-Forwarded-Proto

# --- доверенные источники для CSRF (указывать со схемой!) ---
CSRF_TRUSTED_ORIGINS = [
    "https://promtb-admin.timuroid.ru",  # твой внешний домен из скрина
    # ниже — удобно оставить локалки на время разработки
    "http://localhost:8030",
    "http://127.0.0.1:8030",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


# ────────────────────────────────────────────────────────────────────────────────
# ПРИЛОЖЕНИЯ
# ────────────────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "nested_admin",
    "core",  # ваши модели (помните: managed=False в Meta, чтобы не мигрировать эти таблицы)
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ────────────────────────────────────────────────────────────────────────────────
# БАЗА ДАННЫХ: PostgreSQL (из скрина)
# ────────────────────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "llm",
        "USER": "hrrjskze",
        "PASSWORD": "FNhRJt_eapnjJ4BnzAz9",
        "HOST": "94.241.142.172",
        "PORT": "8083",
        "CONN_MAX_AGE": 60,  # пул соединений
        # Если на сервере нужен TLS, раскомментируйте и выставьте режим:
        # "OPTIONS": {"sslmode": "require"},
    }
}

# ────────────────────────────────────────────────────────────────────────────────
# ЛОКАЛИЗАЦИЯ
# ────────────────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# ────────────────────────────────────────────────────────────────────────────────
# СТАТИКА
# ────────────────────────────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ────────────────────────────────────────────────────────────────────────────────
# ПРОЧЕЕ
# ────────────────────────────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Базовое логирование (удобно видеть ошибки/SQL-подключение)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
}
