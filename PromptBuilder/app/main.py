"""Точка входа FastAPI‑приложения PromptBuilder.

Запуск локально:
    uvicorn PromptBuilder.app.main:app --reload --port 8010
"""
from fastapi import FastAPI, Request
import logging
import time
from uuid import uuid4

from PromptBuilder.core.logging import setup_logging, request_id_var
from PromptBuilder.core.settings import settings

from .routers import router

setup_logging(level=settings.log_level, json_logs=bool(settings.log_json))

logger = logging.getLogger("PromptBuilder.app")

app = FastAPI(
    title="PromptBuilder API",
    version="1.0.0",
    description=("Сервис сборки промптов для двухшагового пайплайна анализа: "
        "Шаг 1 — GroupResult, Шаг 2 — SectionPlanOutput."),
)

app.include_router(router)


@app.middleware("http")
async def _access_log_middleware(request: Request, call_next):
    """Access‑middleware: проставляет request_id и логирует начало/ошибку/завершение запроса."""
    rid = request.headers.get("X-Request-ID") or str(uuid4())
    token = request_id_var.set(rid)
    start = time.monotonic()
    logger.info(
        "request.start method=%s path=%s client=%s rid=%s",
        request.method,
        request.url.path,
        request.client.host if request.client else "-",
        rid,
    )
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request.error method=%s path=%s rid=%s",
            request.method,
            request.url.path,
            rid,
        )
        request_id_var.reset(token)
        raise
    finally:
        dur_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "request.end method=%s path=%s status=%s dur_ms=%s rid=%s",
            request.method,
            request.url.path,
            getattr(response, "status_code", "?"),
            dur_ms,
            rid,
        )
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = rid
    return response

