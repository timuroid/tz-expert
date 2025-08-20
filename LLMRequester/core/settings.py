"""
core/settings.py
Настройки LLM Requester.
Читает YC_* переменные, лимит конкурентности и, при желании, кастомный прайсинг.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    YC_API_KEY: str = Field(..., description="API key for Yandex Foundation Models")
    YC_FOLDER_ID: str = Field(..., description="Folder ID for Yandex Cloud")
    YC_BASE_URL: str = Field("https://llm.api.cloud.yandex.net/v1", description="OpenAI-compatible base URL")

    MAX_CONCURRENT: int = Field(10, description="Семафор на параллельные запросы")

settings = Settings()

