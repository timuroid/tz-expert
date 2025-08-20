"""
schemas.py
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
    groupCode: str                   # код группы (например, "General 1")
    groupName: str                   # название группы (человекочитаемое имя)
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
    # Дополнительно: полная информация по указанной группе-группе (как в latest-gg)
    gg: Optional['GGMeta'] = None
    groups: Optional[List['GGGroup']] = None

    # Разрешаем сериализацию по alias (schema_)
    model_config = ConfigDict(populate_by_name=True)


# ===== Новые схемы для GET latest-gg и POST создания GG =====

class GGMeta(BaseModel):
    """Метаданные Group Group (error_group_groups)."""
    id: int
    name: str


class BaseError(BaseModel):
    """Базовая схема ошибки (общие поля)."""
    code: str
    name: str
    description: str
    detector: str


class GGError(BaseError):
    """Ошибка внутри группы (в выдаче latest-gg присутствует id)."""
    id: int


class GGGroup(BaseModel):
    """Группа ошибок с вложенными ошибками."""
    id: int
    name: str
    code: Optional[str] = None
    groupDescription: Optional[str] = None
    isDeleted: bool
    errors: List[GGError]


class LatestGGResponse(BaseModel):
    """Ответ для GET /latest-gg."""
    ggid: int
    gg: GGMeta
    groups: List[GGGroup]


# ----- POST создание GG -----

class CreateGGError(BaseError):
    pass


class CreateGGGroup(BaseModel):
    name: str
    code: Optional[str] = None
    groupDescription: Optional[str] = None
    isDeleted: bool = False
    errors: List[CreateGGError] = Field(default_factory=list)


class CreateGGRequest(BaseModel):
    """Тело POST: создание нового GG с группами и ошибками."""
    gg: Dict[str, Any] = Field(..., description="Объект GG, минимум name")
    groups: List[CreateGGGroup]


class CreateGGResponse(LatestGGResponse):
    """Возвращаем созданный GG в том же формате, что и latest-gg."""
    pass
