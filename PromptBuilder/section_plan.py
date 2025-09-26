from __future__ import annotations

from typing import List, Optional, Literal

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class ProposedNewSection(BaseModel):
    name: str = Field(..., description="Synthetic section name (Part)")
    suggested_position: Literal["top", "before", "after", "bottom"] = Field(
        ..., description="Where to place it logically"
    )
    position_ref: Optional[str] = Field(
        None, description="Reference section name for before/after (if applicable)"
    )
    reason: str = Field(..., description="Short rationale for placement")


class DuplicateDecision(BaseModel):
    kept_id: str = Field(..., description="Instance ID kept")
    dropped_ids: List[str] = Field(..., description="Instance IDs dropped as duplicates")
    reason: str = Field(..., description="Why kept_id was kept (specificity, priority, lines, etc.)")


class SectionRow(BaseModel):
    part: str = Field(..., description="Canonical section name (real or synthetic)")
    exists_in_doc: bool = Field(..., description="Whether the section exists in the source document")
    initial_instance_ids: List[str] = Field(..., description="All instance IDs before deduplication")
    duplicate_decisions: List[DuplicateDecision] = Field(default_factory=list, description="Decisions taken on duplicates")
    final_instance_ids: List[str] = Field(..., description="Final instance IDs after deduplication")


class SectionPlanOutput(BaseModel):
    doc_title: str = Field(..., description="Document title")
    proposed_new_sections: List[ProposedNewSection] = Field(..., description="New sections proposed and why")
    sections: List[SectionRow] = Field(..., description="Sections in required output order", min_length=1)
    unplaced_instances: List[str] = Field(..., description="Instances that couldn't be placed")
    notes: str = Field(None, description="Short notes on placement/coverage")

    model_config = ConfigDict(extra="forbid")

