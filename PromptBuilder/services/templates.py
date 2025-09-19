"""Template helpers for PromptBuilder."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"

STEP1_SYSTEM = (PROMPT_DIR / "step1.system.md").read_text(encoding="utf-8").strip()
STEP1_USER_TEMPLATE = (PROMPT_DIR / "step1_user.tpl.md").read_text(encoding="utf-8")

STEP2_SYSTEM = (PROMPT_DIR / "step2.system.md").read_text(encoding="utf-8").strip()
STEP2_USER_TEMPLATE = (PROMPT_DIR / "step2_user.tpl.md").read_text(encoding="utf-8")


def _render_errors_block(rules: Iterable[Dict]) -> str:
    blocks: List[str] = []
    for r in rules:
        blocks.append(
            f"{r.get('code', '')} - <{r.get('title', '')}>\n"
            f"Описание: {r.get('description', '')}\n"
            f"Детектор: {r.get('detector', '')}"
        )
    return "\n\n".join(blocks) if blocks else "(нет ошибок)"


def build_system_prompt() -> str:
    """Совместимость со старым интерфейсом (шаг 1 system)."""
    return STEP1_SYSTEM


def build_user_prompt(markdown: str, group_meta: Dict, rules: List[Dict]) -> Tuple[str, str | None]:
    """Совместимость со старым интерфейсом (шаг 1 user)."""
    return build_step1_user(markdown=markdown, group_meta=group_meta, rules=rules), None


def build_step1_user(*, markdown: str, group_meta: Dict, rules: Sequence[Dict]) -> str:
    errors_block = _render_errors_block(rules)
    return STEP1_USER_TEMPLATE.format(
        DOCUMENT=markdown,
        GROUP_ID=(group_meta.get("code") or group_meta.get("group_code") or str(group_meta.get("id", ""))),
        GROUP_TITLE=group_meta.get("name", group_meta.get("group_name", "")),
        GROUP_DESC=group_meta.get("system_prompt") or group_meta.get("group_description", ""),
        ERRORS_BLOCK=errors_block,
    ).strip()


def build_step1_prompt(*, markdown: str, group_meta: Dict, rules: Sequence[Dict]) -> Tuple[str, str]:
    user = build_step1_user(markdown=markdown, group_meta=group_meta, rules=rules)
    return STEP1_SYSTEM, user


def _format_step1_results(step1_results_json: str) -> str:
    return step1_results_json.strip() or "(нет данных)"


def build_step2_prompt(*, markdown: str, step1_results_json: str) -> Tuple[str, str]:
    user = STEP2_USER_TEMPLATE.format(
        DOCUMENT=markdown,
        STEP1_GROUP_RESULTS_JSON_ARRAY=_format_step1_results(step1_results_json),
    ).strip()
    return STEP2_SYSTEM, user
