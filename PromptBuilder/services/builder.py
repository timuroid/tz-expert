"""Service for constructing LLM prompts for the two-step pipeline."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PromptBuilder.schemas import (
    BuildItem,
    Step1BuildRequest,
    Step1BuildResponse,
    Step2BuildRequest,
    Step2BuildResponse,
    StepPrompt,
    step1_output_schema,
    step2_output_schema,
)
from PromptBuilder.services.repository import Repo
from PromptBuilder.services.templates import (
    build_step1_prompt,
    build_step2_prompt,
)


class PromptBuilderService:
    """Constructs system/user prompt pairs for LLM requests."""

    def __init__(self, repo: Repo | None = None) -> None:
        self._repo = repo or Repo()

    def build_items(self, *, markdown: str, gg_id: int) -> List[BuildItem]:
        """Backward-compatible helper returning step-1 items."""
        return self.build_step1_items(markdown=markdown, gg_id=gg_id)

    def build_step1_items(
        self, *, markdown: str, gg_id: int, limit: Optional[int] = None
    ) -> List[BuildItem]:
        groups = self._repo.get_groups_by_ggid(gg_id)
        if limit is not None:
            groups = groups[:limit]

        items: List[BuildItem] = []
        for g in groups:
            rules = self._repo.get_rules_by_ids(g["error_ids"])
            system_msg, user_msg = build_step1_prompt(
                markdown=markdown,
                group_meta={
                    "id": g["group_id"],
                    "code": g["group_code"],
                    "name": g.get("group_name", ""),
                    "group_description": g["group_description"],
                },
                rules=rules,
            )
            items.append(
                BuildItem(
                    groupId=g["group_id"],
                    groupCode=g["group_code"],
                    groupName=g.get("group_name", ""),
                    groupDescription=g["group_description"],
                    errorCodeIds=g["error_ids"],
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                )
            )
        return items

    def build_step1_response(self, req: Step1BuildRequest) -> Step1BuildResponse:
        items = self.build_step1_items(
            markdown=req.markdown,
            gg_id=req.ggid,
            limit=req.limit,
        )
        return Step1BuildResponse(
            ggid=req.ggid,
            items=items,
            schema_=step1_output_schema(),
        )

    def build_step2_prompt(self, req: Step2BuildRequest) -> Step2BuildResponse:
        # PromptBuilder не применяет бизнес-логику: вставляем то, что пришло.
        system_msg, user_msg = build_step2_prompt(
            markdown=req.markdown,
            step1_results_json=req.step1_results,
        )
        return Step2BuildResponse(
            prompt=StepPrompt(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ]
            ),
            schema_=step2_output_schema(),
        )

    def output_schema(self) -> Dict[str, Any]:
        """Default schema for the legacy /build endpoint."""
        return step1_output_schema()
