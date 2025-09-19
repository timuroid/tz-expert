"""Настройки TzeExpert."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TZ_",
        extra="ignore",
        case_sensitive=False,
    )

    PROMPT_BUILDER_URL: str = Field(
        "http://localhost:8010/v1/prompt-builder", description="Базовый URL PromptBuilder"
    )
    LLM_REQUESTER_URL: str = Field(
        "http://localhost:8020/v1/structured", description="Базовый URL LLMRequester"
    )
    LLM_MODEL: Optional[str] = Field(default=None, description="URI модели по умолчанию")
    STEP1_LIMIT: Optional[int] = Field(default=None, description="Необязательное ограничение числа групп на шаге 1")


settings = Settings()


def _join(base: str, path: str) -> str:
    base = base.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def build_prompt_builder_endpoint(path: str) -> str:
    return _join(settings.PROMPT_BUILDER_URL, path)


def build_llm_endpoint(path: str) -> str:
    return _join(settings.LLM_REQUESTER_URL, path)
