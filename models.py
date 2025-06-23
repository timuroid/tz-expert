"""
models.py
----------
Pydantic-DTO: строгая валидация входа/выхода.
"""

from typing import List
from pydantic import BaseModel, Field

# ---------- ВХОД ----------
class AnalyzeRequest(BaseModel):
    html: str = Field(..., description="Документ в HTML")
    codes: List[str] | None = Field(
        None, description="Список кодов; None — проверяем все"
    )

# ---------- ВЫХОД ----------
class Finding(BaseModel):
    paragraph: str              # id <p> или <li>
    quote: str                  # цитата из документа
    advice: str                 # пояснение / рекомендация LLM

class ErrorOut(BaseModel):
    code: str
    title: str
    kind: str                   # Invalid | Bows
    findings: List[Finding]     # >=1 элементов

# + новое
class TokenStat(BaseModel):
    prompt: int
    completion: int
    total: int

class AnalyzeResponse(BaseModel):
    errors: List[ErrorOut]
    tokens: TokenStat          # 👈 добавили

