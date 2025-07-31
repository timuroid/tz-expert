"""
llm.py -> llm_service.py
-------
Асинхронная обёртка над Chat Completion API.
Работает «из коробки» с OpenAI ( https://api.openai.com/v1 ),
но базовый URL и имя модели извлекаются из settings ― их легко
заменить на альтернативный энд-пойнт/модель без правки кода.
"""
import re, json,  httpx
from pathlib import Path
from typing import List, Tuple
from openai import AsyncOpenAI         # официальный клиент ≥ 1.0
from tz_expert.settings import settings            # см. ниже
import asyncio
_YC_CONCURRENCY = asyncio.Semaphore(10)   # столько нам разрешено


JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)  # новая - ищет JSON в markdown-блоках
JSON_SIMPLE_RE = re.compile(r"\{.*\}", re.S)  # для поиска просто JSON без блоков

class LLMError(RuntimeError):
    """Исключение при общении с LLM."""


# ── Загружаем system-prompt-ы и схемы 
PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"

TRIAGE_SYSTEM = (PROMPT_DIR / "triage.system.txt").read_text(encoding="utf-8")
TRIAGE_GROUP_SYSTEM = (PROMPT_DIR / "triage_group.system.txt").read_text(encoding="utf-8")
DEEP_SYSTEM   = (PROMPT_DIR / "deep.system.txt").read_text(encoding="utf-8")

# ------------------------------------------------------------------
#    Инициализируем единственный клиент на всё приложение
#    (он потокобезопасен и переиспользует HTTP-коннекты)
# ------------------------------------------------------------------
# ─── OpenRouter клиент (OpenAI-совместимый) ──────────────────
or_client = AsyncOpenAI(
    api_key=settings.or_api_key,
    base_url=settings.or_base_url,   # "https://openrouter.ai/api/v1"
    default_headers={
        "HTTP-Referer": settings.or_referer,
        "X-Title":      settings.or_title,
    },
    timeout=60,
)

# ─── Yandex GPT сырой HTTP client ─────────────────────────────
yc_client = httpx.AsyncClient(
    base_url="https://llm.api.cloud.yandex.net",
    headers={"Authorization": f"Api-Key {settings.yc_api_key}"},
    timeout=60,
)

# ---------- helpers -------------------------------------------------------


# ------------------------------------------------------------------
#    Функция-обёртка: интерфейс совместим со старой версией
# ------------------------------------------------------------------
def _extract_json(raw: str) -> dict:
    raw = raw.strip()

    # ---------- ищем JSON-тело ----------
    if raw.startswith("{"):
        json_text = raw
    else:
        m = JSON_RE.search(raw) or JSON_SIMPLE_RE.search(raw)
        if not m:
            raise LLMError(f"No JSON found in LLM answer:\n{raw[:300]}")
        json_text = m.group(1) if m.re is JSON_RE else m.group(0)

    # ---------- вырезаем \x00–\x1F, \x7F ----------
    json_text = re.sub(r"[\x00-\x1f\x7f]", "", json_text)

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raise LLMError(f"Invalid JSON from LLM: {e}") from e



async def _call_openrouter(messages: List[dict], model: str):
    resp = await or_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content
    obj = _extract_json(content)
    usage = resp.usage.model_dump()      # в новом SDK есть .model_dump()
    return obj, usage

def _oa_to_yc(messages: List[dict]) -> list[dict]:
    """OpenAI-формат → формат Yandex GPT"""
    return [{"role": m["role"], "text": m["content"]} for m in messages]


async def _call_yandex(messages: List[dict], model_uri: str):
    payload = {
        "modelUri": model_uri,
        "messages": _oa_to_yc(messages),
        "generationOptions": {
            "temperature": 0,
            "output_type": "JSON_OBJECT",
            },
    }
    async with _YC_CONCURRENCY:          # ≤10 одновременных входа
        r = await yc_client.post("/foundationModels/v1/completion", json=payload)
    if r.status_code == 429:
        raise RuntimeError("Yandex quota: 429 Too Many Requests")
    if r.status_code != 200:
        raise RuntimeError(f"YC {r.status_code}: {r.text[:200]}")

    data = r.json()

    # в YC ответе JSON стоит внутри message.text
    text = data["result"]["alternatives"][0]["message"]["text"]
    obj = _extract_json(text)

    usage = data["result"]["usage"]
    usage_dict = {
        "prompt_tokens": int(usage.get("inputTextTokens", 0)),
        "completion_tokens": int(usage.get("completionTokens", 0)),
        "total_tokens": int(usage.get("totalTokens", 0)),
    }   
    return obj, usage_dict

# -----------------------------------------------------------------
#  retry-wrapper: до 2 повторов, если _extract_json бросил LLMError
# -----------------------------------------------------------------
async def _call_with_retry(caller, *args, max_retry: int = 2):
    """
    caller  – функция _call_openrouter или _call_yandex
    args[0] – messages (list[dict]); при повторе добавляем fix-prompt
    """
    messages = list(args[0])
    others   = args[1:]

    for attempt in range(max_retry + 1):
        try:
            return await caller(messages, *others)
        except LLMError as e:
            if "Invalid JSON" not in str(e):
                raise                         # другая причина – пробрасываем
            if attempt == max_retry:
                raise                         # исчерпаны попытки
            messages = messages + [{
                "role": "user",
                "content": (
                    "❗ Формат нарушен. Верни РОВНО валидный JSON-объект."
                ),
            }]

# ─── публичная обёртка ────────────────────────────────────────
async def ask_llm(
        messages: List[dict],
        model: str | None = None
) -> Tuple[dict, dict]:
    """
    • model == None  →  дефолт Qwen-3-235B через OpenRouter
    • model.startswith("openrouter/")   →  отправляем как есть в OpenRouter
    • model.startswith("gpt://")        →  отправляем как есть в Yandex Cloud
    • иначе                              →  считаем строкой-шорткатом Yandex-модели
                                           и просто приклеиваем префикс
                                           gpt://<FOLDER>/ + <model>
    """
    # ---- 0. Дефолт: Qwen 235B (OpenRouter) -------------------
    if not model:
        return await _call_with_retry(_call_openrouter, messages,"qwen/qwen3-235b-a22b-2507")

    # ---- 1. Полный маршрут OpenRouter ------------------------
    if model.startswith("openrouter/"):
        return await _call_with_retry(_call_openrouter, messages, model)

    # ---- 2. Полный URI Yandex Cloud --------------------------
    if model.startswith("gpt://"):
        return await _call_with_retry(_call_yandex, messages, model)


    # ---- 3. Короткое имя Yandex → добавляем префикс ----------
    yc_uri = f"gpt://{settings.yc_folder_id}/{model}"
    return await _call_with_retry(_call_yandex, messages, yc_uri)

