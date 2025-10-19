"""
Pydantic‑модели (DTO) для входа/выхода LLMRequester.

Содержит:
- ChatMessage — одно сообщение чата (role, content).
- RunRequest — вход для вызова LLM (messages, optional schema, model).
- Usage — счётчики токенов.
- Cost — расчётная стоимость в рублях.
- RunResponse — объединённый ответ сервиса.
"""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

Role = Literal["system", "user", "assistant", "tool"]


class ChatMessage(BaseModel):
    """Сообщение чата, совместимое с OpenAI‑форматом."""

    role: Role
    content: str


class RunRequest(BaseModel):
    """
    Запрос на выполнение LLM‑вызова.

    Поля:
    - messages — список сообщений (требуется минимум 2: обычно system+user).
    - schema — опциональная JSON‑схема (через alias `schema_`). Если задана,
      провайдер просится вернуть валидный JSON по этой схеме.
    - model — опциональная модель (короткое имя или полный URI). Если не задана,
      используется DEFAULT_MODEL из настроек.
    """

    messages: List[ChatMessage]
    schema_: Optional[Dict[str, Any]] = Field(default=None, alias="schema")
    model: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class Usage(BaseModel):
    """Статистика расхода токенов провайдером."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Cost(BaseModel):
    """Расчётная стоимость вызова в рублях."""

    currency: Literal["RUB"] = "RUB"
    model_label: str
    price_per_1m: float
    total_rub: float


class RunResponse(BaseModel):
    """
    Ответ сервиса.

    result — либо строка (когда схема не запрашивалась), либо объект/массив JSON.
    usage — счётчики токенов.
    cost — расчётная стоимость в RUB.
    model_uri — фактический URI использованной модели (с учётом папки).
    attempts — общее количество попыток (повторы по провайдеру/JSON).
    """

    result: Union[Dict[str, Any], str]
    usage: Usage
    cost: Cost
    model_uri: str
    attempts: int

