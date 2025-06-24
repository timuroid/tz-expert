"""
llm.py
-------
Асинхронная обёртка над Chat Completion API.
Работает «из коробки» с OpenAI ( https://api.openai.com/v1 ),
но базовый URL и имя модели извлекаются из settings ― их легко
заменить на альтернативный энд-пойнт/модель без правки кода.
"""

from typing import List, Tuple
from openai import AsyncOpenAI           # официальный клиент ≥ 1.0
from settings import settings            # см. ниже

class LLMError(RuntimeError):
    """Исключение при общении с LLM."""

# ------------------------------------------------------------------
# 1. Инициализируем единственный клиент на всё приложение
#    (он потокобезопасен и переиспользует HTTP-коннекты)
# ------------------------------------------------------------------
client = AsyncOpenAI(
    api_key = settings.llm_api_key,   
    base_url = settings.llm_base_url, 
    timeout = 60,                        # сек; равно прежнему httpx-таймауту
    max_retries = 3,                     # авто-повтор 429/5xx с экспон. back-off
)

# ------------------------------------------------------------------
# 2. Функция-обёртка: интерфейс совместим со старой версией
# ------------------------------------------------------------------
async def ask_llm(messages: List[dict]) -> Tuple[str, dict]:
    """
    :param messages: стандартный массив [{role,user|system,content}, …]
    :return: (content, usage) — строка ответа и статистика токенов
    :raises LLMError: при HTTP > 299 или ValidationError в SDK
    """
    try:
        rsp = await client.chat.completions.create(
            model = settings.llm_model,           
            messages = messages,
            response_format = {"type": "json_object"},
            temperature = 0,
        )
    except Exception as exc:
        # перехватываем и заворачиваем в собственное исключение
        raise LLMError(str(exc)) from exc

    # распаковываем первый choice
    content = rsp.choices[0].message.content
    usage   = rsp.usage.model_dump()     # {'prompt_tokens': …, 'completion_tokens': …}
    return content, usage
