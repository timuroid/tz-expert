from __future__ import annotations

from typing import List, Optional, Literal

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict



class ProposedNewSection(BaseModel):
    name: str = Field(..., description="Название синтетической секции (Part)")
    suggested_position: Literal["top", "before", "after", "bottom"] = Field(
        ..., description="Куда логично ставить"
    )
    position_ref: Optional[str] = Field(
        None, description="Опорная секция для before/after (если применимо)"
    )
    reason: str = Field(..., description="Короткое обоснование размещения")

class DuplicateDecision(BaseModel):
    kept_id: str = Field(..., description="Инстанс, который остаётся")
    dropped_ids: List[str] = Field(..., description="Инстансы, убранные как дубли")
    reason: str = Field(..., description="Почему оставили kept_id (специфичность, приоритет, строки и т.п.)")

class SectionRow(BaseModel):
    part: str = Field(..., description="Каноническое имя секции (реальное или синтетическое)")
    exists_in_doc: bool = Field(..., description="Есть ли такая секция в исходном документе")
    initial_instance_ids: List[str] = Field(
        ..., description="Полный список инстансов до дедупликации"
    )
    duplicate_decisions: List[DuplicateDecision] = Field(
        default_factory=list, description="Принятые решения по дублям (может быть пусто)"
    )
    final_instance_ids: List[str] = Field(
        ..., description="Окончательный список инстансов в секции после дедупликации"
    )

class SectionPlanOutput(BaseModel):
    doc_title: str = Field(..., description="Название документа")
    proposed_new_sections: List[ProposedNewSection] = Field(
        default_factory=list, description="Какие новые секции добавлены и почему"
    )
    sections: List[SectionRow] = Field(
        ..., description="Секции в том порядке, как их надо выводить в отчёте"
    )
    unplaced_instances: List[str] = Field(
        default_factory=list, description="Инстансы, которые не удалось привязать к секциям"
    )
    notes: Optional[str] = Field(
        None, description="Короткие комментарии по позиционированию/покрытию"
    )

