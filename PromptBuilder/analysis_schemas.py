# -*- coding: utf-8 -*-
"""Pydantic schemas for the two-step DZExpert pipeline (no custom validators)."""
from __future__ import annotations

from typing import List, Optional, Literal

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Shared types
# ──────────────────────────────────────────────────────────────────────────────

Priority = Literal["low", "medium", "high"]


# ──────────────────────────────────────────────────────────────────────────────
# Step 1 — GroupResult
# ──────────────────────────────────────────────────────────────────────────────


class Step(BaseModel):
    """Single analysis step for an error code."""

    goal: str = Field(
        ..., description="What is being checked on this step (KPI/SLA, методики, диапазоны, ссылки, полнота и т.п.)."
    )
    observed: str = Field(
        ..., description="What was found/verified on the step; include line numbers in square brackets if helpful."
    )


class Verdict(BaseModel):
    """Final conclusion for the error."""

    text_verdict: str = Field(
        ..., description="Short engineering verdict (1–2 предложения со смыслом)."
    )
    status: Literal["ErrorPresence", "NoError"] = Field(
        ..., description="Presence of the issue: ErrorPresence или NoError."
    )


class Instance(BaseModel):
    """Concrete manifestation of the error (one pattern)."""

    id: str = Field(
        ..., description="Short identifier '<ERRORID>-<NN>', e.g. 'E11-1'."
    )
    kind: Literal["Invalid", "Missing"] = Field(
        ..., description="Invalid — элемент есть, но инженерно несостоятелен; Missing — обязательный элемент отсутствует."
    )
    lines: List[int] = Field(
        default_factory=list,
        description="Line numbers. Either all > 0, or exactly [0] for document-wide issues (не смешивать 0 и >0)."
    )
    quotes: List[Optional[str]] = Field(
        default_factory=list,
        description="Quotes matching `lines` 1:1; for [0] use [None]."
    )
    sections: List[str] = Field(
        default_factory=list,
        description="Names of sections affected (если применимо)."
    )
    fix: str = Field(
        ..., description="Инженерно корректное исправление (KPI с единицами, методики/стенды, сценарии и т.п.)."
    )
    risks: str = Field(
        ..., description="Инженерные последствия при отсутствии исправления (приёмка, безопасность, SLA, стандарты)."
    )
    priority: Priority = Field(
        ..., description="Оценка риска: low | medium | high."
    )


class ErrorCheck(BaseModel):
    """Result of checking a single error code inside the group."""

    error_id: str = Field(
        ..., description="Код ошибки как во входных данных (буквы/цифры допускаются)."
    )
    title: str = Field(
        ..., description="Изначальное название ошибки (без перефразирования)."
    )
    analysis_steps: List[Step] = Field(
        default_factory=list,
        description="Последовательность шагов анализа."
    )
    analysis_lines: List[int] = Field(
        default_factory=list,
        description="Номера строк (>0), использованные в анализе (пусто для документ-уровня)."
    )
    critique: str = Field(
        ..., description="Краткие контраргументы/исключения, влияющие на вывод."
    )
    verdict: Verdict = Field(
        ..., description="Финальный вывод по ошибке."
    )
    instances: List[Instance] = Field(
        default_factory=list,
        description="Подтверждённые проявления ошибки (по одному паттерну на инстанс)."
    )


class GroupResult(BaseModel):
    """Ответ по одной группе ошибок (step 1)."""

    group_id: int = Field(
        ..., description="Номер группы ошибок."
    )
    group_title: str = Field(
        ..., description="Название группы ошибок."
    )
    errors: List[ErrorCheck] = Field(
        default_factory=list,
        description="Список проверенных кодов ошибок."
    )


# Alias for backward compatibility with prompts/LLM schema name
Step1GroupResult = GroupResult


# ──────────────────────────────────────────────────────────────────────────────
# Step 2 — FinalReportBySections
# ──────────────────────────────────────────────────────────────────────────────


class SectionIssue(BaseModel):
    """Issue within a specific document section."""

    error_code: str = Field(
        ..., description="Код ошибки в разделе (например, 'E11')."
    )
    rule_title: str = Field(
        ..., description="Полное название ошибки из шага 1."
    )
    instance_ids: List[str] = Field(
        default_factory=list,
        description="Ссылки на id инстансов шага 1 (если применимо)."
    )
    quotes: List[str] = Field(
        default_factory=list,
        description="Цитаты из документа для локализации проблемы (без искажений)."
    )
    what_is_incorrect: str = Field(
        ..., description="Инженерно сформулированная проблема раздела."
    )
    how_to_fix: str = Field(
        ..., description="Конкретные действия для исправления (KPI, методики, сценарии)."
    )
    risk_if_not_fixed: str = Field(
        ..., description="Эксплуатационные/безопасностные последствия при отсутствии исправления."
    )
    priority: Priority = Field(
        ..., description="Приоритет по вашей оценке: low | medium | high."
    )


class SectionReport(BaseModel):
    """Aggregated report for a section."""

    part: str = Field(
        ..., description="Точный заголовок раздела."
    )
    errors_mentioned: List[str] = Field(
        default_factory=list,
        description="Все коды ошибок, упомянутые в разделе."
    )
    summary: str = Field(
        ..., description="Краткое инженерное резюме по разделу."
    )
    errors_present: List[str] = Field(
        default_factory=list,
        description="Ошибки, действительно подтверждённые в разделе."
    )
    issues: List[SectionIssue] = Field(
        default_factory=list,
        description="Детальные проблемы (по одной записи на каждую ошибку)."
    )


class FinalReportBySections(BaseModel):
    """Final consolidated report by sections (step 2)."""

    doc_title: str = Field(
        ..., description="Название документа."
    )
    by_sections: List[SectionReport] = Field(
        default_factory=list,
        description="Список разделов с обнаруженными проблемами."
    )
    document_wide: List[SectionIssue] = Field(
        default_factory=list,
        description="Документ-уровневые проблемы (например, на основе инстансов с lines=[0])."
    )


# Alias for backward compatibility
Step2FinalReport = FinalReportBySections
