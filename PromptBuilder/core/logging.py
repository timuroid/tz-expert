from __future__ import annotations

import json
import logging
import sys
from logging import Handler, LogRecord
from typing import Any, Dict
import contextvars


# Correlation ID (set by HTTP middleware)
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
"""Контекстная переменная с идентификатором запроса (для корреляции логов)."""


class _RequestIdFilter(logging.Filter):
    """Фильтр логов, который добавляет `request_id` в запись лога."""

    def filter(self, record: LogRecord) -> bool:
        rid = request_id_var.get("-")
        if not hasattr(record, "request_id"):
            record.request_id = rid  # type: ignore[attr-defined]
        return True


class _JsonFormatter(logging.Formatter):
    """Простой JSON‑форматтер для логов."""

    def format(self, record: LogRecord) -> str:
        payload: Dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(*, level: str | int = "INFO", json_logs: bool = False) -> None:
    """Инициализировать корневой логгер с форматтером и фильтром request_id.

    Повторные вызовы не дублируют хендлеры — только обновляется уровень и
    гарантируется наличие фильтра.
    """
    root = logging.getLogger()
    if root.handlers:
        # Already configured by the host; just ensure our request-id filter is present
        for h in root.handlers:
            h.addFilter(_RequestIdFilter())
        root.setLevel(level)
        return

    handler: Handler = logging.StreamHandler(stream=sys.stdout)
    handler.addFilter(_RequestIdFilter())
    if json_logs:
        handler.setFormatter(_JsonFormatter())
    else:
        fmt = "%(asctime)s %(levelname)s [%(name)s] [rid=%(request_id)s] %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root.addHandler(handler)
    root.setLevel(level)
