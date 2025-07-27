"""
Orchestration layer: triage-group → triage-single → deep.
Вынесен из старого app.py без изменения логики.
"""
import json, yaml, asyncio, logging
from pathlib import Path
from typing import List, Dict, Tuple

from tz_expert.schemas import (
    AnalyzeRequest, AnalyzeResponse, AnalyzeOut,
    Finding, TokenStat
)
from tz_expert.services.llm_service import (
    ask_llm, LLMError,
    TRIAGE_SYSTEM, TRIAGE_GROUP_SYSTEM, DEEP_SYSTEM
)
from tz_expert.utils.tokens import count_tokens

# ---------- Загрузка YAML-справочников ----------
with open("errors.yaml", encoding="utf-8") as f:
    RULES: Dict[str, dict] = {r["code"]: r for r in yaml.safe_load(f)}

groups_data = yaml.safe_load(Path("groups.yaml").read_text(encoding="utf-8"))
GROUPS_MAP = {g["id"]: g for g in groups_data["groups"]}
DEFAULT_GROUPS = [g["id"] for g in groups_data["groups"]]

# ---------- PROMPT-генераторы ----------
def _triage_prompt(html: str, rule: dict) -> List[dict]:
    return [
        {"role": "system", "content": TRIAGE_SYSTEM},
        {"role": "user",   "content": f"<DOCUMENT>{html}</DOCUMENT>"},
        {"role": "user",   "content":
            f"'Код ошибки' : '{rule['code']}',\n"
            f"'Название ошибки' : '{rule['title']}',\n"
            f"'Описание ошибки' : '{rule['description']}',\n"
            f"'Способ обнаружения ошибки' : '{rule['detector']}'"}
    ]

def _deep_prompt(html: str, rule: dict) -> List[dict]:
    return [
        {"role": "system", "content": DEEP_SYSTEM},
        {"role": "user",   "content": f"<DOCUMENT>{html}</DOCUMENT>"},
        {"role": "user",   "content":
            f"'Код ошибки' : '{rule['code']}',\n"
            f"'Название ошибки' : '{rule['title']}',\n"
            f"'Описание ошибки' : '{rule['description']}',\n"
            f"'Способ обнаружения ошибки' : '{rule['detector']}'"}
    ]

def _triage_group_prompt(html: str, group_def: dict) -> List[dict]:
    body = "\n\n".join(
        f"Код: {RULES[c]['code']}\n"
        f"Название: {RULES[c]['title']}\n"
        f"Описание: {RULES[c]['description']}\n"
        f"Детектор: {RULES[c]['detector']}"
        for c in group_def["codes"]
    )
    return [
        {"role": "system", "content": TRIAGE_GROUP_SYSTEM},
        {"role": "user",   "content": f"<DOCUMENT>{html}</DOCUMENT>"},
        {"role": "user",   "content": group_def["system_prompt"] + body + "\n\n Верни ровно JSON"},
    ]

# ---------- Сервис-класс ----------
class AnalyzerService:
    async def analyze(self, req: AnalyzeRequest) -> AnalyzeResponse:
        model = req.model

        codes  = req.codes  or []
        groups = req.groups or []
        if not codes and not groups:
            groups = DEFAULT_GROUPS

        token_stat = {"prompt": 0, "completion": 0}

        # --- group triage --------------------------------------------------
        async def _triage_group(grp_id: str) -> List[Tuple[str, bool]]:
            obj, usage = await ask_llm(
                _triage_group_prompt(req.html, GROUPS_MAP[grp_id]),
                model=model,
            )
            token_stat["prompt"]     += usage.get("prompt_tokens", 0)
            token_stat["completion"] += usage.get("completion_tokens", 0)
            return [(r["code"], r["exists"]) for r in obj["results"]]

        triage_pairs: List[Tuple[str, bool]] = []
        if groups:
            results = await asyncio.gather(*(_triage_group(g) for g in groups))
            triage_pairs.extend(p for sub in results for p in sub)

        # --- single triage -------------------------------------------------
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
            triage_pairs.extend(
                await asyncio.gather(*(_triage_single(c) for c in codes))
            )

        positives = [c for c, ok in triage_pairs if ok]

        # --- deep ----------------------------------------------------------
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

        token_stat["total"] = token_stat["prompt"] + token_stat["completion"]
        logging.info(
            "tokens_in=%s",
            count_tokens(req.html) * len(codes)
        )
        return AnalyzeResponse(
            errors=detailed,
            tokens=TokenStat(**token_stat)
        )

    # отдельный метод для /errors
    def list_rules(self) -> Dict[str, dict]:
        return RULES
