"""Помощники для загрузки шаблонов и сборки текстов промптов."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple
import logging


# Prompts directory
_PB_ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = _PB_ROOT / "prompts"

_log = logging.getLogger(__name__)

STEP1_SYSTEM = (PROMPT_DIR / "step1.system.md").read_text(encoding="utf-8").strip()
STEP1_USER_TEMPLATE = (PROMPT_DIR / "step1_user.tpl.md").read_text(encoding="utf-8")

STEP2_SYSTEM = (PROMPT_DIR / "step2.system.md").read_text(encoding="utf-8").strip()
STEP2_USER_TEMPLATE = (PROMPT_DIR / "step2_user.tpl.md").read_text(encoding="utf-8")


def _render_errors_block(rules: Iterable[Dict]) -> str:
    """Сформировать текстовый блок перечня правил: код, название, описание, детектор."""
    blocks: List[str] = []
    for r in rules:
        blocks.append(
            f"{r.get('code', '')} - <{r.get('title', '')}>\n"
            f"Описание: {r.get('description', '')}\n"
            f"Детектор: {r.get('detector', '')}"
        )
    return "\n\n".join(blocks) if blocks else "(нет ошибок)"


def build_step1_user(*, markdown: str, group_meta: Dict, rules: Sequence[Dict]) -> str:
    """Собрать пользовательское сообщение для шага 1 по группе правил."""
    errors_block = _render_errors_block(rules)
    user = STEP1_USER_TEMPLATE.format(
        DOCUMENT=markdown,
        GROUP_ID=(group_meta.get("code") or group_meta.get("group_code") or str(group_meta.get("id", ""))),
        GROUP_TITLE=group_meta.get("name", group_meta.get("group_name", "")),
        GROUP_DESC=group_meta.get("system_prompt") or group_meta.get("group_description", ""),
        ERRORS_BLOCK=errors_block,
    ).strip()
    _log.debug(
        "tmpl: step1 user built (doc_len=%s, rules=%s, out_len=%s)",
        len(markdown),
        len(list(rules)),
        len(user),
    )
    return user


def build_step1_prompt(*, markdown: str, group_meta: Dict, rules: Sequence[Dict]) -> Tuple[str, str]:
    """Вернуть пару (system, user) сообщений для шага 1."""
    user = build_step1_user(markdown=markdown, group_meta=group_meta, rules=rules)
    return STEP1_SYSTEM, user


def _format_step1_results(step1_results_json: str) -> str:
    """Аккуратно привести строку JSON с результатами шага 1 к пустому массиву при пустом вводе."""
    return (step1_results_json or "").strip() or "[]"


def build_step2_prompt(*, markdown: str, step1_results_json: str) -> Tuple[str, str]:
    """Вернуть пару (system, user) сообщений для шага 2."""
    user = STEP2_USER_TEMPLATE.format(
        DOCUMENT=markdown,
        STEP1_GROUP_RESULTS_JSON_ARRAY=_format_step1_results(step1_results_json),
    ).strip()
    _log.debug(
        "tmpl: step2 user built (doc_len=%s, step1_json_len=%s, out_len=%s)",
        len(markdown),
        len(step1_results_json or ""),
        len(user),
    )
    return STEP2_SYSTEM, user
