"""
Настройки сервиса LLMRequester (через pydantic‑settings).

Источники переменных окружения (приоритет у более верхнего пункта):
1) Файл рядом с сервисом: `LLMRequester/llmrequester.env`
2) Файл рядом с сервисом: `LLMRequester/.env`
3) Файл в текущей рабочей директории: `./.env`

Все поля ниже можно задать через переменные окружения. Основные из них:
- YC_API_KEY, YC_FOLDER_ID, YC_BASE_URL — параметры доступа к Yandex Cloud.
- MAX_CONCURRENT — ограничение параллелизма обращений к провайдеру.
- HTTP_TIMEOUT — таймаут HTTP‑клиента.
- MAX_RETRY_PROVIDER/MAX_RETRY_JSON — политика повторов по ошибкам провайдера
  и по ошибкам парсинга JSON соответственно.
- DEFAULT_MODEL — модель по умолчанию (хвост URI).
- LOG_LEVEL, REQUEST_LOG, REQUEST_ID_HEADER — параметры логирования.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


# Prefer env files stored alongside the service code, falling back to CWD .env
# Supported (priority):
# 1) LLMRequester/llmrequester.env
# 2) LLMRequester/.env
# 3) ./.env (current working directory)
_SERVICE_DIR = Path(__file__).resolve().parents[1]
_CANDIDATES = [
    _SERVICE_DIR / "llmrequester.env",
    _SERVICE_DIR / ".env",
    Path.cwd() / ".env",
]
ENV_FILE_PATH = str(next((p for p in _CANDIDATES if p.exists()), Path.cwd() / ".env"))


class Settings(BaseSettings):
    """
    Конфигурация сервиса.

    См. модульный docstring для приоритета .env. Поля можно задавать через ENV.
    Наиболее важные поля:
    - YC_API_KEY, YC_FOLDER_ID, YC_BASE_URL — параметры доступа к провайдеру.
    - MAX_CONCURRENT — ограничение параллельных запросов к провайдеру.
    - HTTP_TIMEOUT — таймаут HTTP‑клиента в секундах.
    - MAX_RETRY_PROVIDER — количество повторов при транзиентных ошибках.
    - MAX_RETRY_JSON — количество повторов при невалидном JSON ответе.
    - DEFAULT_MODEL — модель по умолчанию (хвост части URI после folder).
    - LOG_LEVEL, REQUEST_LOG, REQUEST_ID_HEADER — логирование и request‑id.
    """
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        extra="ignore",
        case_sensitive=False,
    )

    YC_API_KEY: str = Field(..., description="API key for Yandex Foundation Models")
    YC_FOLDER_ID: str = Field(..., description="Folder ID for Yandex Cloud")
    YC_BASE_URL: str = Field("https://llm.api.cloud.yandex.net/v1", description="OpenAI-compatible base URL")

    MAX_CONCURRENT: int = Field(10, description="Maximum number of parallel requests to the provider")

    # HTTP client timeout (seconds) for provider calls
    HTTP_TIMEOUT: int = Field(600, description="HTTP timeout seconds for provider calls")

    # Retry policy
    MAX_RETRY_PROVIDER: int = Field(2, description="Retries on transient provider errors")
    MAX_RETRY_JSON: int = Field(2, description="Retries when JSON parsing fails")

    # Default short model name when not provided
    DEFAULT_MODEL: str = Field("qwen3-235b-a22b-fp8/latest", description="Default model suffix or URI last segment")

    # Logging configuration
    LOG_LEVEL: str = Field("INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR")
    REQUEST_LOG: bool = Field(True, description="Enable HTTP request/response logging middleware")
    REQUEST_ID_HEADER: str = Field("X-Request-ID", description="Header used to pass request id")


settings = Settings()
