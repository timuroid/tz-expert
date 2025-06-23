"""
llm.py
-------
Асинхронный адаптер к OpenAI Chat API.
"""

import httpx
from settings import settings

class LLMError(RuntimeError):
    """Ошибка при общении с моделью."""

async def ask_llm(messages: list[dict]) -> str:
    """Отправляет messages → возвращает content первого choice."""
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": settings.openai_model,
        "messages": messages,
        "response_format": {"type": "json_object"},   # просим строгий JSON
        "temperature": 0
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(url, headers=headers, json=payload)
    if r.status_code >= 300:
        raise LLMError(r.text)
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    usage   = data.get("usage", {})              # {prompt_tokens, …}
    return content, usage
