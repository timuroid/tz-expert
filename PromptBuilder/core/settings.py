# PromptBuilder/core/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # читаем .env, игнорируем лишние ключи, префикс PB_, регистр не важен
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="PB_",
        case_sensitive=False,
    )

    # ищется переменная PB_DATABASE_URL (или pb_database_url)
    database_url: str

settings = Settings()
