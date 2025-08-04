"""
analyzer.py  
SGR analyze
"""

import json
import logging
import asyncio
from typing import List, Dict, Tuple

from tz_expert.schemas import (
    StructuredAnalyzeRequest,
    StructuredAnalyzeResponse,
    GroupReportStructured,
    TokenStat,
)
from tz_expert.services.repository import RuleRepository
from tz_expert.services.prompt_builder import build_system_prompt, build_user_prompt
from tz_expert.services.llm_service import ask_llm


class AnalyzerService:
    """
    Сервис для structure-guided reasoning: анализ Markdown по множеству групп.
    """
    def __init__(self, repo: RuleRepository | None = None):
        self._repo = repo or RuleRepository()

    async def analyze_structured(
        self,
        req: StructuredAnalyzeRequest
    ) -> StructuredAnalyzeResponse:
        # 1) Загрузка правил и групп
        groups_map = self._repo.get_all_groups()
        rules_map = self._repo.get_all_rules()

        # 2) Группы из запроса или все
        group_ids = req.groups or list(groups_map.keys())
        invalid = [g for g in group_ids if g not in groups_map]
        if invalid:
            raise ValueError(f"Группы не найдены: {invalid}")

        total_prompt = 0
        total_completion = 0

        async def _analyze_group(gid: str) -> Tuple[GroupReportStructured, Dict[str, int]]:
            meta = groups_map[gid]
            rules = [rules_map[c] for c in meta["codes"]]

            # --- JSON-schema для строгого Structured Output -----------------
            schema_dict = {                       # формат строго ожидаемый ask_llm
                "name":   "GroupReport",          # произвольное осмысленное имя
                "schema": GroupReportStructured.model_json_schema(),
            }

            schema_json = json.dumps(             # ↓ остаётся для prompt-подсказки
                schema_dict["schema"],
                ensure_ascii=False,
                indent=2,
            )

            system_msg = build_system_prompt()
            user_msg = build_user_prompt(
                schema_json=schema_json,
                markdown=req.markdown,
                group_meta=meta,
                rules=rules
            )

            usage_acc = {"prompt_tokens": 0, "completion_tokens": 0}
            max_attempts = 3

            for attempt in range(1, max_attempts + 1):
                messages = [
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": user_msg}
                ]
                if attempt > 1:
                    messages.append({
                        "role": "user",
                        "content": (
                            "❗ Формат ответа нарушен. "
                            "Верните строго валидный JSON по указанной схеме."
                        )
                    })
                try:
                    raw_obj, usage = await ask_llm(messages,schema_dict, model=req.model)
                except Exception as e:
                    logging.warning("Группа %s: LLM-сбой (попытка %d): %s", gid, attempt, e)
                    continue

                usage_acc["prompt_tokens"]     += usage.get("prompt_tokens", 0)
                usage_acc["completion_tokens"] += usage.get("completion_tokens", 0)

                try:
                    report = GroupReportStructured.model_validate(raw_obj)
                    return report, usage_acc
                except Exception as e:
                    logging.warning("Группа %s: неверный JSON (попытка %d): %s", gid, attempt, e)
                    continue

            # stub, если все попытки неудачны
            logging.error("Группа %s: нет валидного JSON после %d попыток", gid, max_attempts)
            stub = GroupReportStructured(
                group_id=gid,
                preliminary_notes="",
                errors=[],
                overall_critique=f"LLM не вернул валидный JSON после {max_attempts} попыток"
            )
            return stub, usage_acc

        # 3) Параллельный запуск
        tasks = [asyncio.create_task(_analyze_group(g)) for g in group_ids]
        results = await asyncio.gather(*tasks)

        # 4) Сбор итогов
        reports: List[GroupReportStructured] = []
        for report, usage in results:
            reports.append(report)
            total_prompt     += usage.get("prompt_tokens", 0)
            total_completion += usage.get("completion_tokens", 0)

        tokens = TokenStat(
            prompt=total_prompt,
            completion=total_completion,
            total=total_prompt + total_completion
        )
        return StructuredAnalyzeResponse(reports=reports, tokens=tokens)
