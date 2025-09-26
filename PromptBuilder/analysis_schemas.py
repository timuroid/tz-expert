# -*- coding: utf-8 -*-
"""Pydantic schemas for the two-step TzeExpert pipeline.

This version makes step-2 schema stricter and removes some fields
from SectionIssue/SectionReport as requested:
  - removed in step 2: rule_title, quotes, errors_mentioned, summary
  - forbid unknown fields (additionalProperties=false) on step-2 models
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
    """Отдельный шаг анализа для конкретного кода ошибки."""

    goal: str = Field(..., description="Что проверяется на данном шаге ")
    observed: str = Field(..., description="Что найдено/проверено на шаге; при необходимости указывайте номера строк")


class Verdict(BaseModel):
    """Итоговый вывод по ошибке."""

    text_verdict: str = Field(..., description="Краткий вердик на основе анализа и критики (1–2 предложения)")
    status: Literal["ErrorPresence", "NoError"] = Field(..., description="Наличие ошибки")


class Instance(BaseModel):
    """Конкретное проявление ошибки (один паттерн)."""

    id: str = Field(..., description="Короткий идентификатор '<ERRORID>-<NN>', напр. 'E11-1'")
    kind: Literal["Invalid", "Missing"] = Field(..., description="Invalid — элемент есть, но несостоятелен; Missing — обязательный элемент отсутствует")
    what_is_incorrect: str = Field(
        ..., description="Что именно некорректно в данном инстансе (кратко и прикладно)"
    )
    lines: List[int] = Field(
        default_factory=list,
        description="Номера строк. Либо все > 0, либо ровно [0] для проблем уровня документа",
    )
    quotes: List[Optional[str]] = Field(
        default_factory=list,
        description="Цитаты, соответствующие `lines` 1:1; для [0] используйте [None]",
    )
    fix: str = Field(
        ..., description="Краткое предложение по исправлению, включая целевой раздел (при необходимости)"
    )
    sections: List[str] = Field(
        default_factory=list,
        description=(
            "Названия целевых разделов, где нужно внести правки; предпочтительно минимальный набор; перечисляйте несколько только если изменения реально требуются в нескольких разделах"
        ),
    )
    risks: str = Field(..., description="Последствия, если не исправить")
    priority: Priority = Field(..., description="Приоритет: low | medium | high")


class ErrorCheck(BaseModel):
    """Результат проверки одного кода ошибки внутри группы."""
    error_id: str = Field(..., description="Код ошибки (напр., E11)")
    title: str = Field(..., description="Короткое человеко-понятное название ошибки")
    analysis_steps: List[Step] = Field(default_factory=list, description="Трассировка выполненных проверок")
    analysis_lines: List[str] = Field(default_factory=list, description="Поддерживающие номера строк (>0)")
    critique: str = Field(..., description="Самокритика / ограничения / оговорки")
    verdict: Verdict = Field(..., description="Итоговое решение по ошибке")
    instances: List[Instance] = Field(default_factory=list, description="Найденные инстансы ошибки")


class GroupResult(BaseModel):
    """Результат по группе ошибок (шаг 1)."""
    group_id: int = Field(..., description="Идентификатор группы ошибок")
    group_title: str = Field(..., description="Название группы ошибок")
    errors: List[ErrorCheck] = Field(default_factory=list, description="Проверки по ошибкам в группе")


# Alias for backward compatibility with prompts/LLM schema name
Step1GroupResult = GroupResult


# =============================
# Step 2 - FinalReportBySections
# =============================


class SectionIssue(BaseModel):
    """Проблема в конкретном разделе или на уровне документа (строго; без лишних полей)."""
    error_code: str = Field(..., description="Код ошибки, встречающийся в этом контексте (напр., 'E11')")
    instance_ids: List[str] = Field(default_factory=list, description="Идентификаторы инстансов с Шага 1")
    what_is_incorrect: str = Field(..., description="где и в чем заключается ошибка")
    how_to_fix: str = Field(..., description="Как исправить")
    risk_if_not_fixed: str = Field(..., description="Риски/последствия, если не исправить")
    priority: Priority = Field(..., description="Приоритет: low | medium | high")

    # запрет неизвестных полей
    model_config = ConfigDict(extra="forbid")


class SectionReport(BaseModel):
    """Сводный отчёт по разделу (строго; без лишних полей)."""
    part: str = Field(..., description="Название раздела")
    errors_present: List[str] = Field(default_factory=list, description="Идентификаторы инстансов, присутствующих в разделе")
    issues: List[SectionIssue] = Field(default_factory=list, description="Детализированные проблемы раздела")

    # запрет неизвестных полей
    model_config = ConfigDict(extra="forbid")


class FinalReportBySections(BaseModel):
    """Итоговый отчёт по разделам (шаг 2, строгая схема)."""
    doc_title: str = Field(..., description="Название документа")
    document_wide: List[SectionIssue] = Field(
        ..., description="Проблемы уровня документа (не привязаны к конкретному разделу)"
    )
    by_sections: List[SectionReport] = Field(
        ..., description="Сводные отчёты по разделам с описанием проблем"
    )

    # запрет неизвестных полей
    model_config = ConfigDict(extra="forbid")


# Alias for backward compatibility
Step2FinalReport = FinalReportBySections
