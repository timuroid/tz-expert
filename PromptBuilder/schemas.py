"""
API DTO для PromptBuilder.

Изменения:
- нет секции meta в ответе;
- в item поле errorCodes переименовано в errorCodeIds;
- схема (JSON Schema) прикладывается один раз на корневом уровне ответа.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class BuildRequest(BaseModel):
    """Вход: Markdown + идентификатор группы групп (ggid)."""
    markdown: str
    ggid: int


class BuildItem(BaseModel):
    """
    Один элемент для LLM-запроса по конкретной группе.
    """
    groupId: int                     # числовой id группы (из БД)
    groupName: str                   # человекочитаемый код, например "G07"
    groupDescription: Optional[str] = None
    errorCodeIds: List[int]          # Список ID ошибок, входящих в группу (именно ID)
    messages: List[Dict[str, str]]   # [{"role":"system","content":"..."}, {"role":"user","content":"..."}]


class BuildResponse(BaseModel):
    """
    Ответ: ggid наверху, список items и ОДНА общая схема.
    """
    ggid: int
    items: List[BuildItem]
    schema_: Dict[str, Any] = Field(..., alias="schema")  # алиас, чтобы ключ в JSON был "schema"

    # Разрешаем сериализацию по alias (schema_)
    model_config = ConfigDict(populate_by_name=True)
