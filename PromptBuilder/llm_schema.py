"""
Pydantic-модели ответа LLM (локальная копия для JSON Schema).
Не импортируем из tz_expert — сервисы изолированы.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

ErrType = Literal["invalid", "missing"]
Verdict = Literal["error_present", "no_error"]

class RetrievalChunk(BaseModel):
    text: str = Field(..., description="Фрагмент документа (≤120 слов)")
    line_start: int = Field(..., ge=1)
    line_end: int = Field(..., ge=1)

class ThoughtProcess(BaseModel):
    retrieval: List[RetrievalChunk]
    analysis: str
    critique: str
    verification: str

class ErrorInstance(BaseModel):
    err_type: ErrType
    snippet: Optional[str] = None
    line_start: Optional[int] = Field(None, ge=1)
    line_end: Optional[int] = Field(None, ge=1)
    suggested_fix: Optional[str] = None
    rationale: str

class ErrorAnalysisStructured(BaseModel):
    code: str
    process: ThoughtProcess
    verdict: Verdict
    instances: List[ErrorInstance]

class GroupReportStructured(BaseModel):
    group_id: str
    preliminary_notes: str
    errors: List[ErrorAnalysisStructured]
    overall_critique: Optional[str] = None
