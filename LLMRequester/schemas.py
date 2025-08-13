"""
Pydantic DTO: вход/выход для LLM Requester (рубли, цены за 1М токенов).
"""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

Role = Literal["system", "user", "assistant", "tool"]

class ChatMessage(BaseModel):
    role: Role
    content: str

class RunRequest(BaseModel):
    """
    Один запуск для одной группы.
    - messages: как минимум 2 сообщения (system, user)
    - schema: опционально; если не задана — вернём текст (string), а не JSON
    - model: опционально; если не задана — yandexgpt/latest
    - mode: опционально; если не задан — "sync"
    """
    messages: List[ChatMessage]
    schema_: Optional[Dict[str, Any]] = Field(
        default=None, 
        alias="schema",
        description="{'name':..., 'schema': {...}}; если None — без Structured Output"
    )
    model: Optional[str] = None
    mode: Optional[Literal["sync", "async"]] = None

    model_config = ConfigDict(populate_by_name=True)

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class Cost(BaseModel):
    currency: Literal["RUB"] = "RUB"
    model_label: str                   # нормализованное имя модели (например, 'yandexgpt-lite')
    mode: Literal["sync", "async"]
    price_per_1m: float                # ₽ за 1 000 000 токенов (включая НДС, по таблице YC)
    total_rub: float                   # итог в ₽ (округление до 6 знаков)

class RunResponse(BaseModel):
    """
    result — либо JSON-объект (dict) при schema!=None, либо строка (raw text).
    """
    result: Union[Dict[str, Any], str]
    usage: Usage
    cost: Cost
    model_uri: str
    attempts: int
