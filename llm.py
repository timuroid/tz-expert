"""
llm.py
-------
Асинхронная обёртка над Chat Completion API.
Работает «из коробки» с OpenAI ( https://api.openai.com/v1 ),
но базовый URL и имя модели извлекаются из settings ― их легко
заменить на альтернативный энд-пойнт/модель без правки кода.
"""
import json
from pathlib import Path
from typing import List, Tuple
from openai import AsyncOpenAI           # официальный клиент ≥ 1.0
from settings import settings            # см. ниже

class LLMError(RuntimeError):
    """Исключение при общении с LLM."""


# ── Загружаем system-prompt-ы и схемы 
PROMPT_DIR = Path(__file__).parent / "prompts"

TRIAGE_SYSTEM = (PROMPT_DIR / "triage.system.txt").read_text(encoding="utf-8")
TRIAGE_GROUP_SYSTEM = (PROMPT_DIR / "triage_group.system.txt").read_text(encoding="utf-8")
DEEP_SYSTEM   = (PROMPT_DIR / "deep.system.txt").read_text(encoding="utf-8")
TRIAGE_SCHEMA = json.loads((PROMPT_DIR / "triage.schema.json").read_text(encoding="utf-8"))
TRIAGE_GROUP_SCHEMA = json.loads((PROMPT_DIR / "triage_group.schema.json").read_text(encoding="utf-8"))
DEEP_SCHEMA   = json.loads((PROMPT_DIR / "deep.schema.json").read_text(encoding="utf-8"))

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
async def ask_llm(messages: List[dict], schema: dict, model: str | None = None) -> Tuple[dict, dict]:
    """
    :param messages: стандартный массив [{role,user|system,content}, …]
    :param schema:   TRIAGE_SCHEMA или DEEP_SCHEMA
    :return: (dict-ответ, usage) — строка ответа и статистика токенов
    """
    chosen_model = model or settings.llm_model

    try:
        rsp = await client.chat.completions.create(
            model = chosen_model,           
            messages = messages,
            functions=[schema],
            function_call={"name": schema["name"]},
            temperature = 0
        )
        call = rsp.choices[0].message.function_call  # JSON-строка
        obj  = json.loads(call.arguments)                                # → dict
        return obj, rsp.usage.model_dump()
    except Exception as exc:
        # перехватываем и заворачиваем в собственное исключение
        raise LLMError(str(exc)) from exc

