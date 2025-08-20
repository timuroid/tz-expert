"""
llm_schema.py
Pydantic-модели ответа LLM (локальная копия для JSON Schema).
Не импортируем из tz_expert — сервисы изолированы.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

ErrType = Literal["invalid", "missing"]
Verdict = Literal["error_present", "no_error"]

class RetrievalChunk(BaseModel):
    text: str = Field(..., description="Фрагмент документа (≤120 слов)")
    line_start: int = Field(..., ge=1, description="Номер начала фрагмента")
    line_end: int = Field(..., ge=1, description="Номер конца фрагмента")

class ThoughtProcess(BaseModel):
    retrieval: List[RetrievalChunk] = Field(
        ..., description="1–5 ключевых фрагментов"
    )
    analysis: str = Field(..., description="Почему это ошибка?")
    critique: str = Field(..., description="Самокритика рассуждений")
    verification: str = Field(..., description="окончательная проверка и вывод")

class ErrorInstance(BaseModel):
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
    code: str = Field(..., description="Код ошибки (E-код)")
    process: ThoughtProcess = Field(..., description="Trace рассуждений")
    verdict: Verdict = Field(
        ..., description="'error_present' или 'no_error'"
    )
    instances: List[ErrorInstance] = Field(
        ..., description="Список найденных/отсутствующих экземпляров"
    )

class GroupReportStructured(BaseModel):
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
