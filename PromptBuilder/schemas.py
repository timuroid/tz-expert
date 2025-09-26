"""
schemas.py
API DTO for PromptBuilder (two-step pipeline).

Purpose:
- DTOs for building prompts per step;
- errorCodeIds stored in BuildItem for prompt context;
- JSON Schemas provided to LLM for strict structured output.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from PromptBuilder.analysis_schemas import GroupResult
from PromptBuilder.section_plan import SectionPlanOutput


class BuildRequest(BaseModel):
    """Input: markdown document + classifier id (ggid)."""

    markdown: str
    ggid: int


class BuildItem(BaseModel):
    """One system/user prompt pair for an error group."""

    groupId: int
    groupCode: str
    groupName: str
    groupDescription: Optional[str] = None
    errorCodeIds: List[int]
    messages: List[Dict[str, str]]  # [{"role": "system", ...}, {"role": "user", ...}]


class BuildResponse(BaseModel):
    """Response of /build: prompts plus schema."""

    ggid: int
    items: List[BuildItem]
    schema_: Dict[str, Any] = Field(..., alias="schema")
    gg: Optional["GGMeta"] = None
    groups: Optional[List["GGGroup"]] = None

    model_config = ConfigDict(populate_by_name=True)


# ===== DTO for GG catalogue management =====


class GGMeta(BaseModel):
    id: int
    name: str


class BaseError(BaseModel):
    code: str
    name: str
    description: str
    detector: str


class GGError(BaseError):
    id: int


class GGGroup(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    groupDescription: Optional[str] = None
    isDeleted: bool
    errors: List[GGError]


class LatestGGResponse(BaseModel):
    ggid: int
    gg: GGMeta
    groups: List[GGGroup]


class CreateGGError(BaseError):
    pass


class CreateGGGroup(BaseModel):
    name: str
    code: Optional[str] = None
    groupDescription: Optional[str] = None
    isDeleted: bool = False
    errors: List[CreateGGError] = Field(default_factory=list)


class CreateGGRequest(BaseModel):
    gg: Dict[str, Any] = Field(..., description="GG metadata (at minimum: name)")
    groups: List[CreateGGGroup]


class CreateGGResponse(LatestGGResponse):
    pass


# ===== DTO for pipeline steps =====


class Step1BuildRequest(BuildRequest):
    """Build prompts for step 1."""

    limit: Optional[int] = Field(default=None, ge=1, description="Optional cap on number of groups")


class StepPrompt(BaseModel):
    messages: List[Dict[str, str]]


class Step1BuildResponse(BaseModel):
    ggid: int
    items: List[BuildItem]
    schema_: Dict[str, Any] = Field(..., alias="schema")

    model_config = ConfigDict(populate_by_name=True)


class Step2BuildRequest(BaseModel):
    markdown: str
    step1_results: str = Field(..., description="JSON array of GroupResult (all groups)")


class Step2BuildResponse(BaseModel):
    prompt: StepPrompt
    schema_: Dict[str, Any] = Field(..., alias="schema")

    model_config = ConfigDict(populate_by_name=True)


# ===== Helpers =====


def step1_output_schema() -> Dict[str, Any]:
    schema = GroupResult.model_json_schema()
    # Ensure top-level required keys include 'errors'
    try:
        props = schema.get("properties", {})
        required = list(schema.get("required", []))
        for k in ("group_id", "group_title", "errors"):
            if k in props and k not in required:
                required.append(k)
        if required:
            schema["required"] = required
        # Dive into $defs to strengthen nested requirements
        defs = schema.get("$defs") or schema.get("definitions") or {}
        ec = defs.get("ErrorCheck")
        if isinstance(ec, dict):
            ec_props = ec.get("properties", {})
            ec_req = list(ec.get("required", []))
            for k in ("error_id", "title", "analysis_steps", "critique", "verdict", "instances"):
                if k in ec_props and k not in ec_req:
                    ec_req.append(k)
            if ec_req:
                ec["required"] = ec_req
        inst = defs.get("Instance")
        if isinstance(inst, dict):
            i_props = inst.get("properties", {})
            i_req = list(inst.get("required", []))
            for k in ("id", "kind", "what_is_incorrect", "lines", "quotes", "fix", "sections", "risks", "priority"):
                if k in i_props and k not in i_req:
                    i_req.append(k)
            if i_req:
                inst["required"] = i_req
    except Exception:
        # if schema structure changes, fail open
        pass
    return {"name": "Step1GroupResult", "schema": schema}


def step2_output_schema() -> Dict[str, Any]:
    return {"name": "SectionPlanOutput", "schema": SectionPlanOutput.model_json_schema()}
