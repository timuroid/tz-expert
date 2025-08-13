"""
Загрузка шаблонов и сборка system/user сообщений.
"""
from pathlib import Path
from typing import Dict, List, Tuple

PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"

STRUCTURE_SYSTEM = (PROMPT_DIR / "structure.system.txt").read_text(encoding="utf-8").strip()
STRUCTURE_USER_TEMPLATE = (PROMPT_DIR / "structure_user.tpl.txt").read_text(encoding="utf-8")

def build_system_prompt() -> str:
    return STRUCTURE_SYSTEM

def _truncate(text: str, limit: int = 20000) -> tuple[str, str | None]:
    if len(text) <= limit:
        return text, None
    return text[:limit], f"Документ усечён до {limit} символов."

def build_user_prompt(markdown: str, group_meta: Dict, rules: List[Dict]) -> Tuple[str, str | None]:
    md, note = _truncate(markdown)
    lines: List[str] = []
    for r in rules:
        lines.append(
            f"{r['code']} — «{r['title']}»\n"
            f"Описание: {r['description']}\n"
            f"Способ Детекции: {r['detector']}"
        )
    errors_block = "\n\n".join(lines)

    prompt = STRUCTURE_USER_TEMPLATE.format(
        DOCUMENT=md,
        GROUP_ID=group_meta["id"],
        GROUP_NAME=group_meta.get("name", ""),
        GROUP_DESC=group_meta.get("system_prompt", ""),
        ERRORS_BLOCK=errors_block,
    ).strip()

    prompt += (
        "\n\n⚠️ ВАЖНО: верните **только** JSON-объект c полями:\n"
        "  - group_id, preliminary_notes, errors, overall_critique;\n"
        "  - не включайте схему или пояснения."
    )
    return prompt, note
