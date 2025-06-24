"""
settings.py
------------
Мини-конфиг через Pydantic BaseSettings.
"""

from pydantic_settings import BaseSettings          
from pydantic import Field    

class Settings(BaseSettings):
    llm_api_key: str = Field(..., env="LLM_API_KEY")         # 🔑
    llm_model: str   = Field("gpt-4o-mini", env="LLM_MODEL") # 🏷
    llm_base_url: str = Field(..., env="LLM_BASE_URL")
    class Config:
        env_file = ".env"                                          # локальный dev

settings = Settings()
