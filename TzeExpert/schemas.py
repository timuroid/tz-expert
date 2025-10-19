"""DTO для API TzeExpert."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel

from PromptBuilder.schemas import GroupResult, SectionPlanOutput


class JobRequest(BaseModel):
    markdown: str
    ggid: int


class Step1Run(BaseModel):
    group_id: int
    raw: str
    parsed: GroupResult


class JobResponse(BaseModel):
    step1: List[Step1Run]
    step2: SectionPlanOutput
