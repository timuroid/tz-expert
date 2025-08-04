from pathlib import Path
from typing import List, Dict

# Путь до папки prompts/structure*.txt
PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"

# Системный prompt для structure-guided reasoning
STRUCTURE_SYSTEM = (
    PROMPT_DIR / "structure.system.txt"
).read_text(encoding="utf-8").strip()
# User-template с плейсхолдерами: ожидает {SCHEMA}, {DOCUMENT}, {GROUP_ID}, {GROUP_NAME}, {GROUP_DESC}, {ERRORS_BLOCK}
STRUCTURE_USER_TEMPLATE = (
    PROMPT_DIR / "structure_user.tpl.txt"
).read_text(encoding="utf-8")


def build_system_prompt() -> str:
    """
    Возвращает системное сообщение для structured analysis.
    """
    return STRUCTURE_SYSTEM


def build_user_prompt(schema_json: str, markdown: str, group_meta: Dict, rules: List[Dict]) -> str:
    """
    Подставляет в шаблон основные части:
      • SCHEMA       — JSON-схема Pydantic-модели (для справки)
      • DOCUMENT     — Markdown документа
      • GROUP_ID     — group_meta['id']
      • GROUP_NAME   — group_meta['name']
      • GROUP_DESC   — group_meta['system_prompt']
      • ERRORS_BLOCK — список правил
    При этом инструкции чётко требуют вернуть только JSON с нужными полями.
    """
    # Формируем блок для каждой ошибки
    lines = []
    for rule in rules:
        lines.append(
            f"{rule['code']} — «{rule['title']}»\n"
            f"Описание: {rule['description']}\n"
            f"Детектор: {rule['detector']}"
        )
    errors_block = "\n\n".join(lines)

    # Привязываем правильные ключи к шаблону
    prompt = STRUCTURE_USER_TEMPLATE.format(
        SCHEMA=schema_json,
        DOCUMENT=markdown,
        GROUP_ID=group_meta['id'],
        GROUP_NAME=group_meta.get('name', ''),
        GROUP_DESC=group_meta.get('system_prompt', ''),
        ERRORS_BLOCK=errors_block
    )
    # Дополнительное требование напоследок
    prompt += (
        "\n\n⚠️ ВАЖНО: верните **только** JSON-объект c полями:\n"
        "  - group_id, preliminary_notes, errors, overall_critique;\n"
        "  - не включайте саму схему или пояснения."
    )
    return prompt.strip()
