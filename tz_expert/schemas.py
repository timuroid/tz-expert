"""
models.py -> schemas.py
----------
Pydantic-DTO: строгая валидация входа/выхода.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict 

# ---------- ВХОД ----------
class AnalyzeRequest(BaseModel):
    html: str = Field(..., description="Документ в HTML")
    codes: Optional[List[str]] = Field(
        None, description="Список кодов для одиночного параллельного прогона; None — не ограничиваем по кодам"
    )
    groups: Optional[List[str]] = Field(
        None, description="Список отдельнх групп для проверки ;  None — используем дефолтные группы, если codes тоже None"
    )
    model: Optional[str] = Field(
        None,
        description=(
            "Название LLM-модели (как в OpenAI API). "
            "Если не указано — берётся из переменной окружения LLM_MODEL"
        ),
        examples=["gpt-4o-mini", "gpt-4o", "anyscale/mistral-8x22b​​​​​"]
    )

    # ⬇️   Дефолтный объект для всего запроса ─────────────────
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "html": "<h1>ТЗ: поставка насосов</h1><p>Описание…</p>",
                    "codes": ["E02"],
                    "groups": ["G02"],
                    "model": "yandexgpt/latest",
                }
            ]
        }
    )

# ---------- ВЫХОД ----------
class Finding(BaseModel):
    kind: str                   # "Invalid" | "Missing"
    paragraph: str               
    quote: str                  # цитата из документа
    advice: str                 # пояснение / рекомендация LLM
    
    class Config:
        extra = "ignore"
       

class AnalyzeOut(BaseModel):
    code: str
    title: str                # Invalid | Bows
    findings: List[Finding]  = Field(default_factory=list)  # пустой список допустим   

# + новое
class TokenStat(BaseModel):
    prompt: int
    completion: int
    total: int

class AnalyzeResponse(BaseModel):
    errors: List[AnalyzeOut]
    tokens: TokenStat          

