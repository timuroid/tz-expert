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
    kind: str                   # "Invalid" | "Missing"
    paragraph: str               # "<p01>" | "<p00>"
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
    tokens: TokenStat          # 👈 добавили

