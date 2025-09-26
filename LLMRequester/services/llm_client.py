"""Async helpers for talking to Yandex Cloud (OpenAI-compatible) models."""
from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
import time
from datetime import datetime, timezone
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


async def _call_openai(payload: Dict[str, Any], telemetry: Optional[Dict[str, Any]] = None):
    """Wrapper around the client with concurrency limiting and optional telemetry."""
    queued_at = datetime.now(timezone.utc).isoformat()
    t_sem_start = time.monotonic()
    async with _SEM:
        t_sem_acq = time.monotonic()
        sem_acquired_at = datetime.now(timezone.utc).isoformat()
        sent_at = datetime.now(timezone.utc).isoformat()
        t_call_start = time.monotonic()
        resp = await _client.chat.completions.create(**payload)  # type: ignore[arg-type]
        t_call_end = time.monotonic()
        received_at = datetime.now(timezone.utc).isoformat()
    if telemetry is not None:
        telemetry.update(
            {
                "queued_at": queued_at,
                "sem_acquired_at": sem_acquired_at,
                "sent_at": sent_at,
                "received_at": received_at,
                "sem_wait_ms": int((t_sem_acq - t_sem_start) * 1000),
                "provider_ms": int((t_call_end - t_call_start) * 1000),
            }
        )
    return resp


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
                "max_concurrent": settings.MAX_CONCURRENT,
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
        delay = 0.1
        for prov_try in range(max_retry_provider + 1):
            total_attempts += 1
            payload = dict(base_payload)
            payload["messages"] = fix_messages

            try:
                _tel: Dict[str, Any] = {}
                resp = await _call_openai(payload, telemetry=_tel)
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

            # Persist telemetry for this attempt
            try:
                telemetry = {
                    **_tel,
                    "attempts_so_far": total_attempts,
                    "fix_try": fix_try,
                    "prov_try": prov_try,
                    "model_uri": model_uri,
                    "messages_len": len(fix_messages),
                    "has_schema": isinstance(json_schema, dict),
                    "schema_name": (json_schema.get("name") if isinstance(json_schema, dict) else None),
                    "provider_id": getattr(resp, "id", None),
                    "usage": {
                        "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                        "completion_tokens": int(usage.get("completion_tokens", 0)),
                        "total_tokens": int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0)),
                    },
                    "content_len": len(content),
                }
                (_LOG_DIR / "last_telemetry.json").write_text(
                    json.dumps(telemetry, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                (_LOG_DIR / f"telemetry_{stamp}.json").write_text(
                    json.dumps(telemetry, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                pass

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
