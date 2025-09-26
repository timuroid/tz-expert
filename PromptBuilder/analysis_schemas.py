"""Pydantic schemas for TzeExpert pipeline (Step 1 and Step 2).

Important change: analysis_lines has been removed from Step 1 models.
Prompts will be updated separately.
"""
from __future__ import annotations

from typing import List, Optional, Literal

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


# Shared types
Priority = Literal["low", "medium", "high"]


# =============================
# Step 1 - GroupResult
# =============================


class Step(BaseModel):
    goal: str = Field(..., description="What is being checked")
    observed: str = Field(..., description="What was observed/verified")


class Verdict(BaseModel):
    text_verdict: str = Field(..., description="Short engineering conclusion (1–2 sentences)")
    status: Literal["ErrorPresence", "NoError"] = Field(..., description="Final status for the error")


class Instance(BaseModel):
    id: str = Field(..., description="Canonical instance id '<ERRORID>-<NN>' (e.g. 'E11-1')")
    kind: Literal["Invalid", "Missing"] = Field(..., description="Invalid or Missing")
    what_is_incorrect: str = Field(..., description="What exactly is incorrect")
    lines: List[int] = Field(default_factory=list, description="Line numbers >0 or [0] for document-wide")
    quotes: List[Optional[str]] = Field(default_factory=list, description="1:1 with lines; for [0] use [null]")
    fix: str = Field(..., description="Concrete fix instruction")
    sections: List[str] = Field(default_factory=list, description="Target section(s) for the fix")
    risks: str = Field(..., description="Consequences if not fixed")
    priority: Priority = Field(..., description="low | medium | high")


class ErrorCheck(BaseModel):
    error_id: str = Field(..., description="Error code (e.g., E11)")
    title: str = Field(..., description="Verbatim rule title from input")
    analysis_steps: List[Step] = Field(default_factory=list, description="Trace of reasoning/verification steps")
    critique: str = Field(..., description="Counter-arguments / caveats")
    verdict: Verdict = Field(..., description="Final verdict")
    instances: List[Instance] = Field(default_factory=list, description="Detected instances")


class GroupResult(BaseModel):
    group_id: int = Field(..., description="Classifier group id (1..10)")
    group_title: str = Field(..., description="Group title")
    errors: List[ErrorCheck] = Field(default_factory=list, description="Errors in the group")


# Alias for backward compatibility with prompts/LLM schema name
Step1GroupResult = GroupResult


# =============================
# Step 2 - FinalReportBySections
# =============================


class SectionIssue(BaseModel):
    error_code: str = Field(..., description="Error code (e.g., 'E11')")
    instance_ids: List[str] = Field(default_factory=list, description="Related instance ids from step 1")
    what_is_incorrect: str = Field(..., description="What is incorrect in this section for the code")
    how_to_fix: str = Field(..., description="How to fix in this section")
    risk_if_not_fixed: str = Field(..., description="Risk/impact if not fixed")
    priority: Priority = Field(..., description="low | medium | high")

    model_config = ConfigDict(extra="forbid")


class SectionReport(BaseModel):
    part: str = Field(..., description="Section name")
    errors_present: List[str] = Field(default_factory=list, description="Error codes present in the section")
    issues: List[SectionIssue] = Field(default_factory=list, description="Issues for this section")

    model_config = ConfigDict(extra="forbid")


class FinalReportBySections(BaseModel):
    doc_title: str = Field(..., description="Document title")
    document_wide: List[SectionIssue] = Field(..., description="Document-wide issues")
    by_sections: List[SectionReport] = Field(..., description="Per-section reports")

    model_config = ConfigDict(extra="forbid")


# Alias for backward compatibility
Step2FinalReport = FinalReportBySections

