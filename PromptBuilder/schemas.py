"""Pydantic‑схемы PromptBuilder: API DTO и доменные модели результатов.
Назначение:
- DTO для шагов сборки промптов;
- доменные модели результата Шага 1 (GroupResult) и Шага 2 (SectionPlanOutput);
- функции, возвращающие именованные JSON Schema для LLM."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from typing import List as _ListTypeAlias  # to avoid name confusion in models below

# ==== Result schemas (moved from analysis_schemas.py and section_plan.py) ====
from typing import Literal


# Shared types
Priority = Literal["low", "medium", "high"]


# =============================
# Step 1 - GroupResult
# =============================


class Step(BaseModel):
    """Шаг анализа в рамках проверки одного правила."""
    goal: str = Field(..., description="What is being checked")
    observed: str = Field(..., description="What was observed/verified")


class Verdict(BaseModel):
    """Вердикт по правилу: краткое заключение и финальный статус."""
    text_verdict: str = Field(..., description="Short engineering conclusion (1–2 sentences)")
    status: Literal["ErrorPresence", "NoError"] = Field(..., description="Final status for the error")


class Instance(BaseModel):
    """Конкретный инстанс нарушения/отсутствия правила в документе."""
    id: str = Field(..., description="Canonical instance id '<ERRORID>-<NN>' (e.g. 'E11-1')")
    kind: Literal["Invalid", "Missing"] = Field(..., description="Invalid or Missing")
    what_is_incorrect: str = Field(..., description="What exactly is incorrect")
    lines: _ListTypeAlias[int] = Field(default_factory=list, description="Line numbers >0 or [0] for document-wide")
    quotes: _ListTypeAlias[Optional[str]] = Field(default_factory=list, description="1:1 with lines; for [0] use [null]")
    fix: str = Field(..., description="Concrete fix instruction")
    sections: _ListTypeAlias[str] = Field(default_factory=list, description="Target section(s) for the fix")
    risks: str = Field(..., description="Consequences if not fixed")
    priority: Priority = Field(..., description="low | medium | high")


class ErrorCheck(BaseModel):
    """Результат проверки одного правила в группе."""
    error_id: str = Field(..., description="Error code (e.g., E11)")
    title: str = Field(..., description="Verbatim rule title from input")
    analysis_steps: _ListTypeAlias[Step] = Field(default_factory=list, description="Trace of reasoning/verification steps")
    critique: str = Field(..., description="Counter-arguments / caveats")
    verdict: Verdict = Field(..., description="Final verdict")
    instances: _ListTypeAlias[Instance] = Field(default_factory=list, description="Detected instances")


class GroupResult(BaseModel):
    """Результат шага 1 по одной группе правил."""
    group_id: int = Field(..., description="Classifier group id (1..10)")
    group_title: str = Field(..., description="Group title")
    errors: _ListTypeAlias[ErrorCheck] = Field(default_factory=list, description="Errors in the group")


# Alias for backward compatibility with prompts/LLM schema name
Step1GroupResult = GroupResult


# =============================
# Step 2 - SectionPlanOutput
# =============================


class ProposedNewSection(BaseModel):
    """Предложение о новом разделе (с пояснением позиции)."""
    name: str = Field(..., description="Synthetic section name (Part)")
    suggested_position: Literal["top", "before", "after", "bottom"] = Field(
        ..., description="Where to place it logically"
    )
    position_ref: Optional[str] = Field(
        None, description="Reference section name for before/after (if applicable)"
    )
    reason: str = Field(..., description="Short rationale for placement")


class DuplicateDecision(BaseModel):
    """Решение о дедупликации инстансов (какой оставлен и почему)."""
    kept_id: str = Field(..., description="Instance ID kept")
    dropped_ids: _ListTypeAlias[str] = Field(..., description="Instance IDs dropped as duplicates")
    reason: str = Field(..., description="Why kept_id was kept (specificity, priority, lines, etc.)")


class SectionRow(BaseModel):
    """Строка финального плана для раздела (существует/нет, финальные инстансы)."""
    part: str = Field(..., description="Canonical section name (real or synthetic)")
    exists_in_doc: bool = Field(..., description="Whether the section exists in the source document")
    initial_instance_ids: _ListTypeAlias[str] = Field(..., description="All instance IDs before deduplication")
    duplicate_decisions: _ListTypeAlias[DuplicateDecision] = Field(default_factory=list, description="Decisions taken on duplicates")
    final_instance_ids: _ListTypeAlias[str] = Field(..., description="Final instance IDs after deduplication")


class SectionPlanOutput(BaseModel):
    """Итоговый план по разделам документа для шага 2."""
    doc_title: str = Field(..., description="Document title")
    proposed_new_sections: _ListTypeAlias[ProposedNewSection] = Field(..., description="New sections proposed and why")
    sections: _ListTypeAlias[SectionRow] = Field(..., description="Sections in required output order", min_length=1)
    unplaced_instances: _ListTypeAlias[str] = Field(..., description="Instances that couldn't be placed")
    notes: str = Field(None, description="Short notes on placement/coverage")

    model_config = ConfigDict(extra="forbid")


class BuildItem(BaseModel):
    """Одна пара сообщений (system/user) для группы правил."""

    groupId: int
    groupCode: str
    groupName: str
    groupDescription: Optional[str] = None
    errorCodeIds: List[int]
    messages: List[Dict[str, str]]  # [{"role": "system", ...}, {"role": "user", ...}]


    


# ===== DTO for GG catalogue management =====


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


    


# ===== DTO for pipeline steps =====


class Step1BuildRequest(BaseModel):
    """Запрос на сборку промптов для шага 1."""
    """Build prompts for step 1."""

    markdown: str
    ggid: int
    limit: Optional[int] = Field(default=None, ge=1, description="Optional cap on number of groups")


class StepPrompt(BaseModel):
    """Обёртка для списка сообщений chat‑формата."""
    messages: List[Dict[str, str]]


class Step1BuildResponse(BaseModel):
    """Ответ шага 1: промпты по группам и именованная JSON Schema результата."""
    ggid: int
    items: List[BuildItem]
    schema_: Dict[str, Any] = Field(..., alias="schema")
    # Additionally return error catalogue for the given ggid
    # Format: groups -> errors -> { code, name, description, detector }
    groups: Optional[List["GGGroup"]] = None

    model_config = ConfigDict(populate_by_name=True)


class Step2BuildRequest(BaseModel):
    """Запрос на сборку промпта для шага 2."""
    markdown: str
    step1_results: str = Field(..., description="JSON array of GroupResult (all groups)")


class Step2BuildResponse(BaseModel):
    """Ответ шага 2: пара сообщений и именованная JSON Schema SectionPlanOutput."""
    prompt: StepPrompt
    schema_: Dict[str, Any] = Field(..., alias="schema")

    model_config = ConfigDict(populate_by_name=True)


# ===== Helpers =====


def step1_output_schema() -> Dict[str, Any]:
    """
    Вернуть именованную JSON Schema результата шага 1 для LLM.
    Схема формируется из модели Pydantic и «усиливается» по required, чтобы\r
    повысить долю валидных ответов от LLM.\r
    """
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
    """Вернуть именованную JSON Schema результата шага 2 для LLM."""
    return {"name": "SectionPlanOutput", "schema": SectionPlanOutput.model_json_schema()}

