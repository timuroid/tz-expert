"""
settings.py
------------
Мини-конфиг через Pydantic BaseSettings.
"""

from pydantic_settings import BaseSettings          
from pydantic import Field    

class Settings(BaseSettings):
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")         # 🔑
    openai_model: str   = Field("gpt-4o-mini", env="OPENAI_MODEL") # 🏷

    class Config:
        env_file = ".env"                                          # локальный dev

settings = Settings()
