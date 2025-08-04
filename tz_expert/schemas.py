"""
schemas.py
----------
Pydantic-DTO: строгая валидация входа/выхода.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

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


# ----------------------------------------------------------------------
# 1) Pydantic-схемы для structure-guided reasoning
# ----------------------------------------------------------------------

# Тип ошибки: invalid = найдено нарушение, missing = чего-то не хватает
ErrType = Literal["invalid", "missing"]
# Вердикт по ошибке: есть ли нарушение
Verdict = Literal["error_present", "no_error"]


class RetrievalChunk(BaseModel):
    """
    Ключевой фрагмент документа, использованный в reasoning.
    """
    text: str = Field(..., description="Фрагмент документа (≤120 слов)")
    line_start: int = Field(..., ge=1, description="Номер начала фрагмента")
    line_end: int = Field(..., ge=1, description="Номер конца фрагмента")


class ThoughtProcess(BaseModel):
    """
    Полный trace рассуждений модели:
      1) retrieval — отрывки
      2) analysis — объяснение
      3) critique — самопроверка
      4) verification — финальная проверка
    """
    retrieval: List[RetrievalChunk] = Field(
        ..., description="1–5 ключевых фрагментов"
    )
    analysis: str = Field(..., description="Почему это ошибка?")
    critique: str = Field(..., description="Самокритика рассуждений")
    verification: str = Field(..., description="окончательная проверка и вывод")


class ErrorInstance(BaseModel):
    """
    Конкретный случай ошибки (или её отсутствие).
    """
    err_type: ErrType = Field(..., description="'invalid' или 'missing'")
    snippet: Optional[str] = Field(
        None, description="Короткая цитата из текста  (≤1 предложение, обычно 3-7 слов)"
    )
    line_start: Optional[int] = Field(
        None, ge=1, description="номер строки начала цитаты"
    )
    line_end: Optional[int] = Field(
        None, ge=1, description="номер строки окончания цитаты"
    )
    suggested_fix: Optional[str] = Field(
        None,
        description="Рекомендация  ≤60 слов",
    )
    rationale: str = Field(..., description="Обоснование решения")




class ErrorAnalysisStructured(BaseModel):
    """
    Результат reasoning по одной ошибке в структуре:
      • code
      • process — полный ThoughtProcess
      • verdict
      • instances
    """
    code: str = Field(..., description="Код ошибки (E-код)")
    process: ThoughtProcess = Field(..., description="Trace рассуждений")
    verdict: Verdict = Field(
        ..., description="'error_present' или 'no_error'"
    )
    instances: List[ErrorInstance] = Field(
        ..., description="Список найденных/отсутствующих экземпляров"
    )


class GroupReportStructured(BaseModel):
    """
    Итоговый отчёт по одной группе ошибок.
    """
    group_id: str = Field(..., description="ID группы (например, G03)")
    preliminary_notes: str = Field(
        ...,
        description="Краткий обзор документа в контексте группы (≤120 слов)"
    )
    errors: List[ErrorAnalysisStructured] = Field(
        ..., description="Анализ по каждой ошибке группы"
    )
    overall_critique: Optional[str] = Field(
        None,
        description="Общее заключение / рекомендации"
    )


class StructuredAnalyzeRequest(BaseModel):
    """
    Запрос на структурированный анализ одной группы.
    """
    markdown: str = Field(..., description="Документ в формате Markdown")
    groups: Optional[List[str]] = Field( None, description="Список ID групп для анализа; None — анализ всех групп")
    model: Optional[str] = Field( None, description="Модель LLM (если не указано — берётся из LLM_MODEL)")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "markdown": "# Заголовок…",
                    "group": ["G02", "G03"],
                    "model": "openrouter/openai/gpt-4o-mini"
                }
            ]
        }
    )

class StructuredAnalyzeResponse(BaseModel):
    """
    Ответ сервиса структурированного анализа —
    список отчётов по группам и статистика токенов.
    """
    reports: List[GroupReportStructured]
    tokens: TokenStat
