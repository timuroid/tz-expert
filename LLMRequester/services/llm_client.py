from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI, OpenAIError  # type: ignore
from LLMRequester.core.settings import settings

_SEM = asyncio.Semaphore(settings.MAX_CONCURRENT)

_client = AsyncOpenAI(
    api_key=settings.YC_API_KEY,
    base_url=settings.YC_BASE_URL,
    timeout=180,
)

_LOG_DIR = Path(__file__).resolve().parents[2] / "llm_requests"
_LOG_DIR.mkdir(exist_ok=True)

class LLMError(RuntimeError):
    """LLM вернул ошибку или невалидный JSON при требуемой схеме."""

def _mk_uri(model: Optional[str]) -> str:
    if not model:
        return f"gpt://{settings.YC_FOLDER_ID}/yandexgpt/latest"
    if model.startswith("gpt://"):
        return model
    return f"gpt://{settings.YC_FOLDER_ID}/{model}"

async def _call_openai(payload: Dict[str, Any]):
    async with _SEM:
        return await _client.chat.completions.create(**payload)  # type: ignore

async def ask_llm(
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]] = None,
    *,
    model: Optional[str] = None,
    max_retry_provider: int = 2,   # повторы на 429/5xx/таймаут
    max_retry_json: int = 2,       # повторы при невалидном JSON
) -> Tuple[Dict[str, Any] | str, Dict[str, int], str, int]:
    """
    Возвращает (result, usage_total, model_uri, attempts_total).

    - Если schema=None → возвращаем сырой текст (string), без Structured Output.
    - Иначе → включаем json_schema и при невалидном JSON пытаемся до max_retry_json раз,
      добавляя «фикс-промпт».
    - На сетевые/квотные ошибки пробуем до max_retry_provider раз с бэкоффом.

    usage_total суммирует usage всех попыток.
    """
    model_uri = _mk_uri(model)

    # лёгкий лог
    _LOG_DIR.joinpath("last_request.json").write_text(
        json.dumps(
            {"model_uri": model_uri, "schema_name": (json_schema or {}).get("name")},
            ensure_ascii=False, indent=2
        ),
        encoding="utf-8"
    )

    base_payload: Dict[str, Any] = {
        "model": model_uri,
        "messages": messages,
        "temperature": 0,
        "stream": False,
    }
    if json_schema is not None:
        base_payload["response_format"] = {"type": "json_schema", "json_schema": json_schema}

    total_attempts = 0
    usage_acc = {"prompt_tokens": 0, "completion_tokens": 0}

    fix_messages = list(messages)  # не трогаем оригинал
    for fix_try in range(max_retry_json + 1):
        # провайдерские ретраи
        delay = 0.2
        for prov_try in range(max_retry_provider + 1):
            total_attempts += 1
            payload = dict(base_payload)
            payload["messages"] = fix_messages

            try:
                resp = await _call_openai(payload)
            except OpenAIError as e:
                # повторяем только на «временные» ошибки
                msg = str(e).lower()
                transient = any(x in msg for x in ("429", "rate limit", "timeout", "gateway", "temporarily"))
                if prov_try < max_retry_provider and transient:
                    await asyncio.sleep(delay + random.random() * 0.2)
                    delay = min(delay * 2, 2.0)
                    continue
                raise LLMError(str(e)) from e

            content = resp.choices[0].message.content or ""
            usage = resp.usage.model_dump() if hasattr(resp, "usage") else {}
            usage_acc["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
            usage_acc["completion_tokens"] += int(usage.get("completion_tokens", 0))

            # если схемы нет — возвращаем сырой текст
            if json_schema is None:
                usage_acc["total_tokens"] = usage_acc["prompt_tokens"] + usage_acc["completion_tokens"]
                return content, usage_acc, model_uri, total_attempts

            # иначе пытаемся распарсить JSON
            try:
                parsed = json.loads(content)
                usage_acc["total_tokens"] = usage_acc["prompt_tokens"] + usage_acc["completion_tokens"]
                return parsed, usage_acc, model_uri, total_attempts
            except Exception:
                # если ещё есть попытки исправить JSON — добавим фикс-промпт и повторим
                break  # выходим из провайдерского цикла к добавлению фикс-промпта

        # сюда попадаем, если JSON сломан и есть ещё попытки fix
        if fix_try < max_retry_json and json_schema is not None:
            fix_messages = fix_messages + [{
                "role": "user",
                "content": "❗ Верни РОВНО валидный JSON-объект по указанной схеме. "
                           "Без Markdown, без комментариев и пояснений."
            }]
            continue

        # исчерпали попытки починить JSON
        raise LLMError(f"Model did not return valid JSON after {max_retry_json + 1} attempts")
