"""
services/llm_schema.py
Pydantic-модели ожидаемого ответа LLM и генератор JSON Schema.
НЕ импортируем ничего из других сервисов — полная изоляция.
"""
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

# Типы
ErrType = Literal["invalid", "missing"]
Verdict = Literal["error_present", "no_error"]

class RetrievalChunk(BaseModel):
    text: str = Field(..., description="Фрагмент документа (≤120 слов)")
    line_start: int = Field(..., ge=1, description="Номер начала фрагмента")
    line_end: int = Field(..., ge=1, description="Номер конца фрагмента")

class ThoughtProcess(BaseModel):
    retrieval: List[RetrievalChunk] = Field(..., description="1–5 ключевых фрагментов")
    analysis: str = Field(..., description="Почему это ошибка?")
    critique: str = Field(..., description="Самокритика рассуждений")
    verification: str = Field(..., description="Окончательная проверка и вывод")

class ErrorInstance(BaseModel):
    err_type: ErrType = Field(..., description="'invalid' или 'missing'")
    snippet: Optional[str] = Field(None, description="Короткая цитата (≤1 предложение)")
    line_start: Optional[int] = Field(None, ge=1, description="Старт цитаты")
    line_end: Optional[int] = Field(None, ge=1, description="Конец цитаты")
    suggested_fix: Optional[str] = Field(None, description="Рекомендация  ≤60 слов")
    rationale: str = Field(..., description="Обоснование решения")

class ErrorAnalysisStructured(BaseModel):
    code: str = Field(..., description="Код ошибки (E-код)")
    process: ThoughtProcess = Field(..., description="Trace рассуждений")
    verdict: Verdict = Field(..., description="'error_present' или 'no_error'")
    instances: List[ErrorInstance] = Field(..., description="Экземпляры ошибки")

class GroupReportStructured(BaseModel):
    group_id: str = Field(..., description="ID группы (например, G03)")
    preliminary_notes: str = Field(..., description="Краткий обзор (≤120 слов)")
    errors: List[ErrorAnalysisStructured] = Field(..., description="Анализ по каждой ошибке")
    overall_critique: Optional[str] = Field(None, description="Общее заключение/рекомендации")

def default_structured_output_schema() -> Dict[str, Any]:
    """
    Возвращает JSON Schema для response_format=json_schema в формате,
    которого ожидает OpenAI-совместимый эндпоинт Яндекса:
    { "name": "<любое имя>", "schema": <pydantic-json-schema> }
    """
    return {
        "name": "GroupReport",
        "schema": GroupReportStructured.model_json_schema(),
    }
