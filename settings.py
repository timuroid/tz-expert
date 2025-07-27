"""
settings.py
------------
Мини-конфиг через Pydantic BaseSettings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ---------- OpenRouter ----------
    or_api_key: str = Field(..., env='OPENROUTER_API_KEY')
    or_base_url: str = 'https://openrouter.ai/v1'
    or_referer: str  = Field(..., env='OPENROUTER_REFERER')   # например https://tz-expert.app
    or_title:   str  = Field('TZ-Expert', env='OPENROUTER_TITLE')

    # ---------- Yandex GPT ----------
    yc_api_key: str  = Field(..., env='YC_API_KEY')
    yc_folder_id: str = Field(..., env='YC_FOLDER_ID')        # b1g…*
    yc_model_uri: str | None = Field(None, env='YC_MODEL_URI')

    # ---------- LLM Model ----------
    llm_model: str = Field('openrouter/openai/gpt-4o-mini', env='LLM_MODEL')  # <- добавьте эту строку

    @property
    def yc_model(self) -> str:
        """uri вида gpt://<folder>/yandexgpt/latest"""
        return self.yc_model_uri or f"gpt://{self.yc_folder_id}/yandexgpt/latest"

    class Config:
        env_file = ".env"


settings = Settings()
