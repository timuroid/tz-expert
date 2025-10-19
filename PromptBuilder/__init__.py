"""PromptBuilder — пакет для сборки промптов (system/user) и выдачи JSON Schema
для двухшагового пайплайна анализа документа LLM‑моделью.

Основные задачи пакета:
- Подготовка сообщений и схемы для шага 1 (GroupResult) по группам правил.
- Подготовка сообщений и схемы для шага 2 (SectionPlanOutput) по итогам шага 1.

Пакет включает FastAPI‑приложение, сервисы обработки (builder/repository/templates),
инфраструктуру (db/settings/logging) и модели (ORM и Pydantic).
"""

