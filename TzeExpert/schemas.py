"""DTO для работы TzeExpert."""
from __future__ import annotations

from typing import List, Any, Dict, Optional

from pydantic import BaseModel

from PromptBuilder.analysis_schemas import (
    GroupResult,
    FinalReportBySections,
)


class JobRequest(BaseModel):
    markdown: str
    ggid: int


class Step1Run(BaseModel):
    group_id: int
    raw: str
    parsed: GroupResult


class JobResponse(BaseModel):
    step1: List[Step1Run]
    step2: FinalReportBySections


class ReportFromResponseRequest(BaseModel):
    """Generate DOCX from a full LLM response JSON.

    Accepts the full JSON object as stored by LLMRequesterClient (with keys like
    status/url/result/...) or a plain RunResponse-like object (with result/usage/...)
    or directly the final report object (doc_title, document_wide, by_sections).
    Optional run_id and ggid can be supplied for filename composition.
    """

    envelope: Dict[str, Any]
    run_id: Optional[str] = None
    ggid: Optional[int] = None


class ReportFromResponseResponse(BaseModel):
    """Response with saved DOCX path and parsed report structure."""

    path: str
    report: FinalReportBySections
