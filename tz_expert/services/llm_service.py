"""
llm_service.py
==============
Минимальная обёртка для вызова **Yandex GPT** через OpenAI‑совместимый
endpoint (`https://llm.api.cloud.yandex.net/v1`).

✔ Поддерживает *Structured Output* (`response_format=json_schema`)
✔ Ограничивает конкурентность через семафор
✔ Имеет простой retry по JSON‑ошибкам
✔ Работает целиком на `openai.AsyncOpenAI`, без `httpx`

Переменные (`settings.py`):
• `yc_api_key`          – API‑ключ «ФМ‑модели: пользователь»
• `yc_folder_id`        – ID каталога‑проекта
• `yc_max_concurrent`   – (int) лимит параллельных запросов, default = 10
• `yc_base_url`         – при необходимости иной базовый URL
"""

from __future__ import annotations

import asyncio
import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from openai import AsyncOpenAI, OpenAIError  # type: ignore
from tz_expert.settings import settings

__all__ = ["LLMError", "ask_llm"]


_LOG_DIR = Path(__file__).resolve().parents[2] / "llm_requests"
_LOG_DIR.mkdir(exist_ok=True)

_SEM = asyncio.Semaphore(10)

_client = AsyncOpenAI(
    api_key=settings.yc_api_key,
    base_url=getattr(settings, "yc_base_url", "https://llm.api.cloud.yandex.net/v1"),
    timeout=60,
)


class LLMError(RuntimeError):
    """LLM прислал невалидный JSON."""


def _mk_uri(model: str | None) -> str:
    
    if model is None:
        return f"gpt://{settings.yc_folder_id}/yandexgpt/latest"
    
    
    return f"gpt://{settings.yc_folder_id}/{model}"


async def _chat_once(messages: List[Dict[str, str]], *, model_uri: str, schema: Dict[str, Any], ) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """Один запрос без ретраев."""
    resp = await _client.chat.completions.create(
        model=model_uri,
        messages=messages,
        temperature=0,
        response_format={"type": "json_schema", "json_schema": schema},
        stream=False,
    )
    try:
        result = json.loads(resp.choices[0].message.content or "{}")
    except (TypeError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise LLMError(str(exc)) from exc
    return result, resp.usage.model_dump()


async def ask_llm(messages: List[Dict[str, str]], json_schema: Dict[str, Any], model: str | None = None, * , max_retry: int = 2,) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """Возвращает `(ответ, usage)`.

    * `messages`    – стандартный список OpenAI‑сообщений.
    * `json_schema` – Pydantic‑schema для Structured Output.
    * `model`       – alias, полный URI или `None` (по умолчанию latest).
    * `max_retry`   – повтор при JSON‑ошибке (≤ 2).
    """

    uri = _mk_uri(model)

    # лог (fire & forget)
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    (_LOG_DIR / f"{ts}.json").write_text(json.dumps({
        "model_uri": uri,
        "messages": messages,
        "schema_name": json_schema.get("name"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    async with _SEM:
        for attempt in range(max_retry + 1):
            try:
                return await _chat_once(messages, model_uri=uri, schema=json_schema)
            except LLMError:
                raise  # JSON сломался – ретрай бессмысленен
            except OpenAIError as err:
                if "json" not in str(err).lower() or attempt == max_retry:
                    raise  # проблема не в JSON или попытки исчерпаны
                # добавляем «fix‑prompt» и пытаемся ещё
                messages = messages + [{
                    "role": "user",
                    "content": "❗ Верни РОВНО валидный JSON‑объект.",
                }]

    raise AssertionError("unreachable")
