"""
Точка входа FastAPI‑приложения LLMRequester.

Запуск локально: uvicorn LLMRequester.app.main:app --reload --port 8020

В этом модуле:
- Глобальная настройка логирования на основе переменных окружения.
- Middleware для логирования входящих HTTP‑запросов (start/end, статус, длительность)
  и для прокидывания request‑id через заголовок.
- Подключение роутов API.
"""
from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request

from LLMRequester.core.settings import settings
from .routers import router


def _configure_logging() -> None:
    """
    Настроить базовую конфигурацию логирования.

    Уровень берётся из settings.LOG_LEVEL. Формат включает время, уровень,
    имя логгера и номер строки для удобства диагностики.
    """
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s:%(lineno)d %(message)s",
    )


_configure_logging()
logger = logging.getLogger("LLMRequester.app")

app = FastAPI(
    title="LLM Requester API",
    version="1.0.0",
    description="HTTP API for calling OpenAI-compatible LLMs (Yandex Cloud).",
)


if settings.REQUEST_LOG:
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        """
        Логирование всех HTTP‑запросов с измерением длительности.

        - На входе создаёт/считывает request‑id и логирует начало запроса.
        - На выходе добавляет заголовок с request‑id, логирует статус и длительность.
        - При ошибках логирует stacktrace вместе с request‑id и длительностью.
        """
        req_id = request.headers.get(settings.REQUEST_ID_HEADER) or uuid4().hex
        start = time.perf_counter()
        try:
            logger.info(
                "request start id=%s %s %s", req_id, request.method, request.url.path
            )
            response = await call_next(request)
            duration_ms = int((time.perf_counter() - start) * 1000)
            response.headers[settings.REQUEST_ID_HEADER] = req_id
            logger.info(
                "request end   id=%s status=%s duration_ms=%s",
                req_id,
                getattr(response, "status_code", "?"),
                duration_ms,
            )
            return response
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.exception("request error id=%s duration_ms=%s", req_id, duration_ms)
            raise


app.include_router(router)

