"""Async helpers for talking to Yandex Cloud (OpenAI-compatible) models."""
from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI, OpenAIError  # type: ignore
from LLMRequester.core.settings import settings

# Limit concurrent requests to the provider
_SEM = asyncio.Semaphore(settings.MAX_CONCURRENT)

# Shared OpenAI-compatible client for the configured Yandex Cloud endpoint
_client = AsyncOpenAI(
    api_key=settings.YC_API_KEY,
    base_url=settings.YC_BASE_URL,
    timeout=600,  # generous HTTP timeout for long generations
)

# Directory for logging last request/response payloads
_LOG_DIR = Path(__file__).resolve().parents[2] / "llm_requests"
_LOG_DIR.mkdir(exist_ok=True)


class LLMError(RuntimeError):
    """Raised when the provider cannot return a valid structured response."""


def _mk_uri(model: Optional[str]) -> str:
    """Construct Yandex Cloud URIs from either short labels or full URIs."""
    if not model:
        return f"gpt://{settings.YC_FOLDER_ID}/qwen3-235b-a22b-fp8/latest"
    if model.startswith("gpt://"):
        return model
    return f"gpt://{settings.YC_FOLDER_ID}/{model}"


async def _call_openai(payload: Dict[str, Any]):
    """Thin wrapper around the AsyncOpenAI client with concurrency limiting."""
    async with _SEM:
        return await _client.chat.completions.create(**payload)  # type: ignore[arg-type]


async def ask_llm(
    messages: List[Dict[str, str]],
    json_schema: Optional[Dict[str, Any]] = None,
    *,
    model: Optional[str] = None,
    max_retry_provider: int = 2,
    max_retry_json: int = 2,
) -> Tuple[Dict[str, Any] | str, Dict[str, int], str, int]:
    """Call the provider with optional JSON-schema forcing and retry logic."""

    model_uri = _mk_uri(model)

    # Log last request metadata for debugging
    (_LOG_DIR / "last_request.json").write_text(
        json.dumps(
            {
                "model_uri": model_uri,
                "schema_name": (json_schema.get("name") if isinstance(json_schema, dict) else None),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    base_payload: Dict[str, Any] = {
        "model": model_uri,
        "messages": messages,
        "temperature": 0,
        "stream": False,
    }
    if isinstance(json_schema, dict):
        base_payload["response_format"] = {"type": "json_schema", "json_schema": json_schema}

    total_attempts = 0
    usage_acc = {"prompt_tokens": 0, "completion_tokens": 0}

    fix_messages = list(messages)
    for fix_try in range(max_retry_json + 1):
        delay = 0.2
        for prov_try in range(max_retry_provider + 1):
            total_attempts += 1
            payload = dict(base_payload)
            payload["messages"] = fix_messages

            try:
                resp = await _call_openai(payload)
            except OpenAIError as e:
                msg = str(e).lower()
                transient = any(keyword in msg for keyword in ("429", "rate limit", "timeout", "gateway", "temporar", "unavailable"))
                if prov_try < max_retry_provider and transient:
                    await asyncio.sleep(delay + random.random() * 0.2)
                    delay = min(delay * 2, 2.0)
                    continue
                raise LLMError(str(e)) from e

            content = resp.choices[0].message.content or ""
            usage = resp.usage.model_dump() if hasattr(resp, "usage") else {}
            usage_acc["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
            usage_acc["completion_tokens"] += int(usage.get("completion_tokens", 0))

            if not isinstance(json_schema, dict):
                usage_acc["total_tokens"] = usage_acc["prompt_tokens"] + usage_acc["completion_tokens"]
                return content, usage_acc, model_uri, total_attempts

            try:
                parsed = json.loads(content)
                if not isinstance(parsed, (dict, list)):
                    raise ValueError(f"Expected JSON object/array, got {type(parsed).__name__}")
                usage_acc["total_tokens"] = usage_acc["prompt_tokens"] + usage_acc["completion_tokens"]
                return parsed, usage_acc, model_uri, total_attempts
            except Exception:
                break

        if fix_try < max_retry_json and isinstance(json_schema, dict):
            fix_messages = fix_messages + [
                {
                    "role": "user",
                    "content": (
                        "Ответ не соответствует запрошенной JSON-схеме. "
                        "Повтори ответ строго в требуемом формате, без пояснений."
                    ),
                }
            ]
            continue

        raise LLMError(f"Model did not return valid JSON after {max_retry_json + 1} attempts")
