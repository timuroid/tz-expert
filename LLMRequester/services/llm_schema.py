"""Pydantic schema used to build JSON Schema for structured output."""
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

ErrType = Literal["invalid", "missing"]
Verdict = Literal["error_present", "no_error"]


class RetrievalChunk(BaseModel):
    text: str = Field(..., description="Snippet of source text (≤120 chars)")
    line_start: int = Field(..., ge=1, description="First line number in the snippet")
    line_end: int = Field(..., ge=1, description="Last line number in the snippet")


class ThoughtProcess(BaseModel):
    retrieval: List[RetrievalChunk] = Field(..., description="1-5 retrieved fragments")
    analysis: str = Field(..., description="Reasoning/analysis text")
    critique: str = Field(..., description="Self critique")
    verification: str = Field(..., description="Verification notes")


class ErrorInstance(BaseModel):
    err_type: ErrType = Field(..., description="invalid | missing")
    snippet: Optional[str] = Field(None, description="Optional text snippet")
    line_start: Optional[int] = Field(None, ge=1, description="Start line number")
    line_end: Optional[int] = Field(None, ge=1, description="End line number")
    suggested_fix: Optional[str] = Field(None, description="Suggested fix in plain text")
    rationale: str = Field(..., description="Why this is an issue")


class ErrorAnalysisStructured(BaseModel):
    code: str = Field(..., description="Error code")
    process: ThoughtProcess = Field(..., description="Trace of reasoning")
    verdict: Verdict = Field(..., description="error_present | no_error")
    instances: List[ErrorInstance] = Field(..., description="Instances discovered")


class GroupReportStructured(BaseModel):
    group_id: str = Field(..., description="Classifier group id")
    preliminary_notes: str = Field(..., description="Short notes about the group")
    errors: List[ErrorAnalysisStructured] = Field(..., description="Analysed errors")
    overall_critique: Optional[str] = Field(None, description="Optional overall critique")


def default_structured_output_schema() -> Dict[str, Any]:
    """Return JSON schema usable in response_format=json_schema."""
    return {
        "name": "GroupReport",
        "schema": GroupReportStructured.model_json_schema(),
    }
