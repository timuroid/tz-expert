"""Service for constructing LLM prompts for the two-step pipeline."""
from __future__ import annotations

import logging
from typing import List, Optional

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
    """Сервис сборки сообщений system/user и JSON Schema для шагов 1 и 2.

    - Шаг 1: по группам правил собирает `BuildItem[]` и схему результата
      (`step1_output_schema`).
    - Шаг 2: собирает итоговый промпт по результатам шага 1 и схему
      `SectionPlanOutput`.
    """

    def __init__(self, repo: Repo | None = None) -> None:
        """Инициализация сервиса.

        repo: источник данных каталога групп/правил. Если не передан, создаётся
        дефолтный `Repo()`.
        """
        self._repo = repo or Repo()
        self._log = logging.getLogger(__name__)

    def build_step1_items(
        self, *, markdown: str, gg_id: int, limit: Optional[int] = None
    ) -> List[BuildItem]:
        """Собрать список промптов (system/user) для шага 1 по группам GG.

        markdown: исходный документ
        gg_id: идентификатор каталога групп
        limit: опциональный лимит количества групп
        """
        self._log.info("step1: fetching groups (ggid=%s, limit=%s)", gg_id, limit)
        groups = self._repo.get_groups_by_ggid(gg_id)
        self._log.info("step1: found %s groups before limit", len(groups))
        if limit is not None:
            groups = groups[:limit]
            self._log.info("step1: applying limit -> %s groups", len(groups))

        items: List[BuildItem] = []
        for g in groups:
            rules = self._repo.get_rules_by_ids(g["error_ids"])
            self._log.debug(
                "step1: build group id=%s code=%s rules=%s",
                g["group_id"],
                g.get("group_code"),
                len(rules),
            )
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
        self._log.info("step1: built %s prompt items", len(items))
        return items

    def build_step1_response(self, req: Step1BuildRequest) -> Step1BuildResponse:
        """Сформировать полный ответ API для шага 1 (items + schema + groups)."""
        items = self.build_step1_items(
            markdown=req.markdown,
            gg_id=req.ggid,
            limit=req.limit,
        )
        gg_full = self._repo.get_gg_full(req.ggid)
        groups = gg_full.get("groups") if gg_full else None
        self._log.info(
            "step1: response ready (items=%s, groups_meta=%s)",
            len(items),
            len(groups or []),
        )
        return Step1BuildResponse(
            ggid=req.ggid,
            items=items,
            schema_=step1_output_schema(),
            groups=groups,
        )

    def build_step2_prompt(self, req: Step2BuildRequest) -> Step2BuildResponse:
        """Собрать промпт для шага 2 и вернуть его вместе со схемой вывода."""
        self._log.info(
            "step2: building prompt (markdown_len=%s, step1_json_len=%s)",
            len(req.markdown),
            len(req.step1_results),
        )
        system_msg, user_msg = build_step2_prompt(
            markdown=req.markdown,
            step1_results_json=req.step1_results,
        )
        self._log.info(
            "step2: prompt built (messages=2, system_len=%s, user_len=%s)",
            len(system_msg),
            len(user_msg),
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
