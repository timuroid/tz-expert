"""
Клиент LLMRequester для обращения к моделям Yandex Cloud (OpenAI‑совместимый API).

Задачи модуля:
- Управление конкурентностью запросов к провайдеру (семафор).
- Унифицированная обработка ошибок с маппингом на HTTP‑статусы (LLMError).
- Повторы (retry) при транзиентных ошибках провайдера и при ошибках JSON‑парсинга.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI, OpenAIError  # type: ignore

try:  # Лучшее усилие: типы ошибок могут отличаться по версиям SDK
    from openai import (
        APIError as _APIError,
        APIConnectionError as _APIConnectionError,
        RateLimitError as _RateLimitError,
        APITimeoutError as _APITimeoutError,
    )  # type: ignore[attr-defined]
except Exception:  # pragma: no cover — необязательно для работы
    _APIError = _APIConnectionError = _RateLimitError = _APITimeoutError = ()  # type: ignore

from LLMRequester.core.settings import settings


# Ограничение параллелизма обращений к провайдеру
_SEM = asyncio.Semaphore(settings.MAX_CONCURRENT)
logger = logging.getLogger(__name__)

# Общий клиент для OpenAI‑совместимого эндпойнта (Yandex Cloud)
_client = AsyncOpenAI(
    api_key=settings.YC_API_KEY,
    base_url=settings.YC_BASE_URL,
    timeout=settings.HTTP_TIMEOUT,
)


class LLMError(RuntimeError):
    """
    Структурированная ошибка уровня клиента LLM.

    Поля используются роутером для возврата корректного статуса и детального
    описания причины.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 422,
        code: str = "provider_error",
        provider_status: Optional[int] = None,
        attempts: Optional[int] = None,
        model_uri: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.provider_status = provider_status
        self.attempts = attempts
        self.model_uri = model_uri


def _mk_uri(model: Optional[str]) -> str:
    """
    Сконструировать URI модели Yandex Cloud.

    Принимает короткое имя (например, "yandexgpt" или "llama-lite") либо полный
    URI вида "gpt://<folder>/<model>[/latest]". Если модель не указана — берётся
    значение из настроек (DEFAULT_MODEL).
    """
    if not model:
        return f"gpt://{settings.YC_FOLDER_ID}/{settings.DEFAULT_MODEL}"
    if model.startswith("gpt://"):
        return model
    return f"gpt://{settings.YC_FOLDER_ID}/{model}"


async def _call_openai(payload: Dict[str, Any]):
    """
    Вызвать OpenAI‑совместимый клиент с ограничением конкурентности.

    Оборачивает реальный HTTP‑вызов семафором, чтобы не превышать лимит
    одновременных запросов к провайдеру.
    """
    async with _SEM:
        return await _client.chat.completions.create(**payload)  # type: ignore[arg-type]


async def ask_llm(
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]] = None,
    *,
    model: Optional[str] = None,
    max_retry_provider: Optional[int] = None,
    max_retry_json: Optional[int] = None,
) -> Tuple[Dict[str, Any] | str, Dict[str, int], str, int]:
    """
    Вызвать провайдера с опциональным принуждением формата JSON по схеме.

    Поведение:
    - Формирует payload из сообщений и (при наличии) JSON‑схемы.
    - Управляет повторными попытками (на транзиентные ошибки провайдера и на
      ошибки парсинга JSON), с экспоненциальной задержкой.
    - При успехе возвращает:
        • либо строку (когда схема не задана),
        • либо dict/list (когда схема задана и контент корректный JSON),
      а также usage (токены), фактический URI модели и количество попыток.
    - При неуспехе бросает LLMError с кодом причины и корректным статусом.

    Возврат:
        (result, usage_totals, model_uri, total_attempts)
    """

    model_uri = _mk_uri(model)

    base_payload: Dict[str, Any] = {
        "model": model_uri,
        "messages": messages,
        "temperature": 0,
        "stream": False,
    }
    if isinstance(json_schema, dict):
        base_payload["response_format"] = {"type": "json_schema", "json_schema": json_schema}

    # Политика ретраев: берём из настроек при отсутствии явных значений
    if max_retry_provider is None:
        max_retry_provider = settings.MAX_RETRY_PROVIDER
    if max_retry_json is None:
        max_retry_json = settings.MAX_RETRY_JSON

    total_attempts = 0
    usage_totals = {"prompt_tokens": 0, "completion_tokens": 0}

    fix_messages = list(messages)
    for fix_try in range(max_retry_json + 1):
        delay = 0.1
        for prov_try in range(max_retry_provider + 1):
            total_attempts += 1
            payload = dict(base_payload)
            payload["messages"] = fix_messages

            try:
                resp = await _call_openai(payload)
            except OpenAIError as e:
                # Классификация ошибок провайдера
                msg = str(e)
                lower = msg.lower()
                http_status = int(getattr(e, "status_code", 0) or getattr(e, "status", 0) or 0)
                transient = (
                    isinstance(e, (_RateLimitError, _APITimeoutError, _APIConnectionError, _APIError))
                    or any(k in lower for k in ("429", "rate limit", "timeout", "gateway", "temporar", "unavailable"))
                )
                if prov_try < max_retry_provider and transient:
                    logger.warning(
                        "ask_llm: transient provider error (attempt=%s/%s fix_try=%s/%s): %s",
                        prov_try + 1,
                        max_retry_provider + 1,
                        fix_try + 1,
                        max_retry_json + 1,
                        e,
                    )
                    await asyncio.sleep(delay + random.random() * 0.2)
                    delay = min(delay * 2, 2.0)
                    continue
                # Маппинг ошибок на статус/код
                if isinstance(e, _RateLimitError) or "429" in lower or "rate limit" in lower:
                    status_code = 429
                    code = "rate_limited"
                elif isinstance(e, _APITimeoutError) or "timeout" in lower:
                    status_code = 504
                    code = "timeout"
                elif isinstance(e, _APIConnectionError) or "gateway" in lower or "unavailable" in lower:
                    status_code = 502
                    code = "connection_error"
                elif http_status == 401:
                    status_code = 401
                    code = "unauthorized"
                elif http_status == 403:
                    status_code = 403
                    code = "forbidden"
                elif http_status == 400:
                    status_code = 400
                    code = "bad_request"
                elif http_status >= 500:
                    status_code = 502
                    code = "upstream_error"
                else:
                    status_code = 422
                    code = "provider_error"
                logger.error("ask_llm: provider error (no retry): %s", e)
                raise LLMError(
                    msg,
                    status_code=status_code,
                    code=code,
                    provider_status=(http_status or None),
                    attempts=total_attempts,
                    model_uri=model_uri,
                ) from e

            content = resp.choices[0].message.content or ""
            usage = resp.usage.model_dump() if hasattr(resp, "usage") else {}
            usage_totals["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
            usage_totals["completion_tokens"] += int(usage.get("completion_tokens", 0))

            if not isinstance(json_schema, dict):
                usage_totals["total_tokens"] = usage_totals["prompt_tokens"] + usage_totals["completion_tokens"]
                return content, usage_totals, model_uri, total_attempts

            try:
                parsed = json.loads(content)
                if not isinstance(parsed, (dict, list)):
                    raise ValueError(f"Expected JSON object/array, got {type(parsed).__name__}")
                usage_totals["total_tokens"] = usage_totals["prompt_tokens"] + usage_totals["completion_tokens"]
                return parsed, usage_totals, model_uri, total_attempts
            except Exception:
                logger.debug(
                    "ask_llm: JSON parse failed on attempt=%s (fix_try=%s)",
                    total_attempts,
                    fix_try + 1,
                )
                break

        if fix_try < max_retry_json and isinstance(json_schema, dict):
            # Дополнительная подсказка модели: вернуть ОДИН валидный JSON без
            # комментариев и лишнего текста строго по схеме.
            fix_messages = fix_messages + [
                {
                    "role": "user",
                    "content": (
                        "Верни только один валидный JSON строго по переданной схеме. "
                        "Без пояснений, комментариев и лишнего текста."
                    ),
                }
            ]
            continue

        raise LLMError(
            f"Model did not return valid JSON after {max_retry_json + 1} attempts",
            status_code=422,
            code="json_parse_failed",
            attempts=total_attempts,
            model_uri=model_uri,
        )

