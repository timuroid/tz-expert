"""
llm.py
-------
Асинхронная обёртка над Chat Completion API.
Работает «из коробки» с OpenAI ( https://api.openai.com/v1 ),
но базовый URL и имя модели извлекаются из settings ― их легко
заменить на альтернативный энд-пойнт/модель без правки кода.
"""
import re, json
from pathlib import Path
from typing import List, Tuple
from openai import AsyncOpenAI           # официальный клиент ≥ 1.0
from settings import settings            # см. ниже

JSON_RE = re.compile(r"\{.*?\}", re.S)     # первый {...}

class LLMError(RuntimeError):
    """Исключение при общении с LLM."""


# ── Загружаем system-prompt-ы и схемы 
PROMPT_DIR = Path(__file__).parent / "prompts"

TRIAGE_SYSTEM = (PROMPT_DIR / "triage.system.txt").read_text(encoding="utf-8")
TRIAGE_GROUP_SYSTEM = (PROMPT_DIR / "triage_group.system.txt").read_text(encoding="utf-8")
DEEP_SYSTEM   = (PROMPT_DIR / "deep.system.txt").read_text(encoding="utf-8")
#TRIAGE_SCHEMA = json.loads((PROMPT_DIR / "triage.schema.json").read_text(encoding="utf-8"))
#TRIAGE_GROUP_SCHEMA = json.loads((PROMPT_DIR / "triage_group.schema.json").read_text(encoding="utf-8"))
#DEEP_SCHEMA   = json.loads((PROMPT_DIR / "deep.schema.json").read_text(encoding="utf-8"))

# ------------------------------------------------------------------
#    Инициализируем единственный клиент на всё приложение
#    (он потокобезопасен и переиспользует HTTP-коннекты)
# ------------------------------------------------------------------
client = AsyncOpenAI(
    api_key = settings.llm_api_key,   
    base_url = settings.llm_base_url, 
    timeout = 60,                        # сек; равно прежнему httpx-таймауту
    max_retries = 3,                     # авто-повтор 429/5xx с экспон. back-off
)

# ------------------------------------------------------------------
#    Функция-обёртка: интерфейс совместим со старой версией
# ------------------------------------------------------------------
def _extract_json(raw: str) -> dict:
    """
    • Если строка начинается на '{' → сразу json.loads
    • Иначе ищем первый {...} или код-блок ```{ … }```
    """
    raw = raw.strip()
    if raw.startswith("{"):
        return json.loads(raw)
    m = JSON_RE.search(raw)
    if not m:
        raise LLMError(f"No JSON found in LLM answer:\n{raw[:300]}")
    return json.loads(m.group(0))


async def ask_llm(messages: list[dict],
                  model: str | None = None) -> tuple[dict, dict]:
    """OpenAI-совместимый вызов без Function Calling"""
    rsp = await client.chat.completions.create(
        model=model or settings.llm_model,
        messages=messages,
        temperature=0
    )
    obj = _extract_json(rsp.choices[0].message.content)
    return obj, rsp.usage.model_dump()

