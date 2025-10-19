"""Конфигурация PromptBuilder через переменные окружения (pydantic-settings).

Читает `.env` в рабочей директории и переменные с префиксом `PB_`.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pydantic-класс настроек сервиса."""
    # Read from .env in the working directory, use PB_* prefix for vars
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="PB_",
        case_sensitive=False,
    )

    # Database connection string (PB_DATABASE_URL)
    database_url: str

    # Logging configuration
    log_level: str = "INFO"   # PB_LOG_LEVEL
    log_json: bool = False    # PB_LOG_JSON


settings = Settings()
