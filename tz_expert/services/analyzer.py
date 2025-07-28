"""
analyzer.py  
Orchestration layer: triage-group → triage-single → deep.
"""

import json
import asyncio
import logging
from typing import List, Dict, Tuple

from tz_expert.schemas import (
    AnalyzeRequest, AnalyzeResponse,
    AnalyzeOut, Finding, TokenStat
)
from tz_expert.services.llm_service import (
    ask_llm, LLMError,
    TRIAGE_SYSTEM, TRIAGE_GROUP_SYSTEM, DEEP_SYSTEM
)
from tz_expert.utils.tokens import count_tokens
from tz_expert.services.repository import RuleRepository

# Одна сессия репозитория на модуль
repo = RuleRepository()


# ---------- PROMPT-генераторы ----------
def _triage_prompt(html: str, rule: dict) -> List[dict]:
    return [
        {"role": "system", "content": TRIAGE_SYSTEM},
        {"role": "user",   "content": f"<DOCUMENT>{html}</DOCUMENT>"},
        {"role": "user",   "content":
            f"'Код ошибки' : '{rule['code']}',\n"
            f"'Название ошибки' : '{rule['title']}',\n"
            f"'Описание ошибки' : '{rule['description']}',\n"
            f"'Способ обнаружения ошибки' : '{rule['detector']}'"
        }
    ]


def _deep_prompt(html: str, rule: dict) -> List[dict]:
    return [
        {"role": "system", "content": DEEP_SYSTEM},
        {"role": "user",   "content": f"<DOCUMENT>{html}</DOCUMENT>"},
        {"role": "user",   "content":
            f"'Код ошибки' : '{rule['code']}',\n"
            f"'Название ошибки' : '{rule['title']}',\n"
            f"'Описание ошибки' : '{rule['description']}',\n"
            f"'Способ обнаружения ошибки' : '{rule['detector']}'"
        }
    ]


def _triage_group_prompt(
    html: str,
    group_def: dict,
    rules: Dict[str, dict]
) -> List[dict]:
    """
    group_def["system_prompt"] теперь — это описание группы из БД.
    rules — полный словарь {code → rule}.
    """
    # Формируем тело из всех кодов группы
    body = "\n\n".join(
        f"Код: {rules[code]['code']}\n"
        f"Название: {rules[code]['title']}\n"
        f"Описание: {rules[code]['description']}\n"
        f"Детектор: {rules[code]['detector']}"
        for code in group_def["codes"]
    )

    return [
        {"role": "system",  "content": TRIAGE_GROUP_SYSTEM},
        {"role": "user",    "content": f"<DOCUMENT>{html}</DOCUMENT>"},
        {"role": "user",    "content": group_def["system_prompt"] + body + "\n\n Верни ровно JSON"},
    ]


# ---------- Сервис-класс ----------
class AnalyzerService:
    async def analyze(self, req: AnalyzeRequest) -> AnalyzeResponse:
        model = req.model

        # 1) Всегда берём самые свежие данные из БД
        RULES      = repo.get_all_rules()    # { "E02": {...}, ... }
        GROUPS_MAP = repo.get_all_groups()   # { "G01": {...}, ... }
        DEFAULT_GROUPS = list(GROUPS_MAP.keys())

        # 2) Коды и группы из запроса
        codes  = req.codes  or []
        groups = req.groups or []
        if not codes and not groups:
            groups = DEFAULT_GROUPS

        token_stat = {"prompt": 0, "completion": 0}
        triage_pairs: List[Tuple[str, bool]] = []

        # --- group triage ---
        async def _triage_group(grp_id: str) -> List[Tuple[str, bool]]:
            obj, usage = await ask_llm(
                _triage_group_prompt(req.html, GROUPS_MAP[grp_id], RULES),
                model=model,
            )
            token_stat["prompt"]     += usage.get("prompt_tokens", 0)
            token_stat["completion"] += usage.get("completion_tokens", 0)
            return [(r["code"], r["exists"]) for r in obj["results"]]

        if groups:
            tasks = (_triage_group(g) for g in groups)
            results = await asyncio.gather(*tasks)
            triage_pairs.extend(p for sub in results for p in sub)

        # --- single triage ---
        async def _triage_single(code: str) -> Tuple[str, bool]:
            rule = RULES[code]
            try:
                obj, usage = await ask_llm(
                    _triage_prompt(req.html, rule),
                    model=model,
                )
                token_stat["prompt"]     += usage.get("prompt_tokens", 0)
                token_stat["completion"] += usage.get("completion_tokens", 0)
                return code, obj.get("exists", False)
            except Exception as exc:
                logging.error("LLM triage error %s: %s", code, exc)
                return code, False

        if codes:
            tasks = (_triage_single(c) for c in codes)
            triage_pairs.extend(await asyncio.gather(*tasks))

        positives = [c for c, ok in triage_pairs if ok]

        # --- deep analysis ---
        async def _deep(code: str) -> AnalyzeOut:
            rule = RULES[code]
            try:
                obj, usage = await ask_llm(
                    _deep_prompt(req.html, rule),
                    model=model,
                )
                token_stat["prompt"]     += usage.get("prompt_tokens", 0)
                token_stat["completion"] += usage.get("completion_tokens", 0)
                findings = [Finding(**f) for f in obj.get("findings", [])]
                return AnalyzeOut(code=obj["code"], title=obj["title"], findings=findings)
            except (LLMError, json.JSONDecodeError) as exc:
                logging.error("LLM deep error %s: %s", code, exc)
                return AnalyzeOut(
                    code=rule["code"],
                    title=rule["title"],
                    findings=[Finding(paragraph="?", quote="-", advice=str(exc))]
                )

        detailed = await asyncio.gather(*(_deep(c) for c in positives))

        # 3) Финальная статистика токенов
        token_stat["total"] = token_stat["prompt"] + token_stat["completion"]
        logging.info("tokens_in=%s", count_tokens(req.html) * len(codes))

        return AnalyzeResponse(errors=detailed, tokens=TokenStat(**token_stat))

    def list_rules(self) -> Dict[str, dict]:
        """Эндпоинт /errors — возвращаем полный справочник из БД."""
        return repo.get_all_rules()
