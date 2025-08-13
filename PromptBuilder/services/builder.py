"""
Фасад: markdown + gg_id -> List[BuildItem] и общая JSON Schema.

Изменения:
- в BuildItem записываем errorCodeIds вместо errorCodes;
- в ответе схемой управляет вызывающий (router), тут только метод output_schema().
"""
from typing import List, Dict, Any
from PromptBuilder.schemas import BuildItem
from PromptBuilder.services.repository import Repo
from PromptBuilder.services.templates import build_system_prompt, build_user_prompt
from PromptBuilder.llm_schema import GroupReportStructured


class PromptBuilderService:
    """Высокоуровневый сервис сборки messages для LLM по группам внутри gg_id."""

    def __init__(self, repo: Repo | None = None):
        self._repo = repo or Repo()

    def output_schema(self) -> Dict[str, Any]:
        """
        Возвращает JSON Schema для Structured Output.
        Её кладём на корневой уровень ответа (не в каждый item).
        """
        return {"name": "GroupReport", "schema": GroupReportStructured.model_json_schema()}

    def build_items(self, *, markdown: str, gg_id: int) -> List[BuildItem]:
        """
        Собирает список BuildItem по всем группам внутри указанного gg_id.
        """
        groups = self._repo.get_groups_by_ggid(gg_id)
        items: List[BuildItem] = []

        for g in groups:
            # Для текста промпта нужны детальные сведения об ошибках (код/описание/детектор)
            rules = self._repo.get_rules_by_ids(g["error_ids"])

            # System/User сообщения
            system_msg = build_system_prompt()

            # mini-адаптер метаданных для шаблона (чтобы не менять templates.py)
            meta_for_template = {
                "id": g["group_code"],                      # подставим и как GROUP_ID, и как GROUP_NAME
                "name": g["group_code"],
                "system_prompt": g["group_description"],
            }
            user_msg, _note = build_user_prompt(
                markdown=markdown,
                group_meta=meta_for_template,
                rules=rules
            )

            # Новый формат item
            items.append(BuildItem(
                groupId=g["group_id"],
                groupName=g["group_code"],
                groupDescription=g["group_description"],
                errorCodeIds=g["error_ids"],               # <-- переименованное поле
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": user_msg},
                ],
            ))

        return items
