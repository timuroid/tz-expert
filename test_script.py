"""
ТЗ‑Expert — одноразовый CLI‑скрипт для проверки Markdown‑документа
на группу ошибок (например, G03) с помощью LLM, доступной через
OpenRouter.

Файл может служить референсом и основой для более сложного пайплайна.

────────────────────────────────────────────────────────────────────────────
Зависимости
───────────
• Python ≥ 3.9
• pydantic
• pyyaml
• requests (или openai‑python, если предпочитаете)  
  pip install pydantic pyyaml requests

Корневая структура проекта (относительно этого скрипта)
────────────────────────────────────────────────────────
./
├── groups.yaml       # id   | name | description
├── errors.yaml       # code | group_id | user_friendly_name | short_criterion | full_description | detection_hint
├── sample.md         # Markdown‑документ для теста
└── tz_audit.py       # ← текущий файл

Запуск
──────
$ export OPENROUTER_API_KEY="sk‑..."
$ python tz_audit.py --group G03 --markdown sample.md

По завершении в stdout печатается одна строка JSON, которую можно
сохранить или распарсить как отчёт.
"""

# ─────────────────────────── imports ──────────────────────────────
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from textwrap import dedent
from typing import List, Literal, Optional
import codecs

import requests
import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator
# ── в самом верху файла ─────────────────────────────
from dotenv import load_dotenv  # pip install python-dotenv
load_dotenv()                   # подхватывает ключи из .env

# ── там, где читаем ключ ────────────────────────────
api_key = (
    os.getenv("OR_API_KEY")   # основное имя       # резервное, как в вашем .env
)
if not api_key:
    sys.exit("❌ Не найден OPENROUTER_API_KEY (или OR_API_KEY) в окружении")

# ──────────────────────── Pydantic схемы ──────────────────────────
# NB: «Allowed codes» будет динамически подменяться в runtime
#     (см. build_schema_classes).

ErrType  = Literal["invalid", "missing"]
Verdict  = Literal["error_present", "no_error"]

class RetrievalChunk(BaseModel):
    """Отрывок Markdown, на который LLM опиралась при анализе."""

    text: str = Field(..., description="Отрывок (≤120 слов)")
    line_start: int = Field(..., ge=1)
    line_end: int = Field(..., ge=1)

class ThoughtProcess(BaseModel):
    """Полный trace рассуждений — retrieval → analysis → critique → verification."""

    retrieval: List[RetrievalChunk] = Field(..., description="1–5 ключевых фрагментов")
    analysis: str = Field(..., description="Почему это ошибка?")
    critique: str = Field(..., description="Самопроверка и поиск слабых мест")
    verification: str = Field(..., description="Финальное подтверждение решения")

class ErrorInstance(BaseModel):
    """Конкретное проявление ошибки (или её отсутствия)."""

    err_type: ErrType
    snippet: Optional[str] = Field(
        None, description="Цитата (для invalid)"
    )
    line_start: Optional[int] = Field(None, ge=1)
    line_end: Optional[int] = Field(None, ge=1)
    suggested_fix: Optional[str] = Field(
        None,
        description="Как исправить или что добавить (для missing) ≤60 слов",
    )
    rationale: str = Field(..., description="Обоснование, почему это ошибка")

    @model_validator(mode="after")
    def _consistency(self) -> "ErrorInstance":
        # self — это валидный инстанс ErrorInstance
        if self.err_type == "invalid":
            if not (self.snippet and self.line_start and self.line_end):
                raise ValueError("'invalid' требует snippet, line_start и line_end")
        else:  # missing
            if any([self.snippet, self.line_start, self.line_end]):
                raise ValueError("'missing' не содержит snippet/line_*")
        return self

# ErrorAnalysisDeep и GroupReport будут сгенерированы динамически,
# потому что поле code зависит от выбранной группы.

# ─────────────────────── YAML helpers ─────────────────────────────

def read_markdown(path: Path) -> str:
    """
    Читаем текст с автоматическим определением кодировки.
    Поддержка: UTF-8 / UTF-8-BOM / UTF-16 LE/BE / Windows-1251.
    """
    # 1) Пробуем UTF-8 / UTF-8-BOM
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        pass

    # 2) Пробуем UTF-16 (BOM нужен)
    try:
        with path.open("rb") as fh:
            raw = fh.read()
        for enc in ("utf-16", "utf-16-le", "utf-16-be"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
    except Exception:
        pass

    # 3) Фолбэк на cp1251
    return path.read_text(encoding="cp1251", errors="replace")

def load_yaml(path: Path) -> list[dict]:
    """Чтение YAML и приведение к списку объектов.

    Поддерживаем оба варианта структуры:
    1) «Плоский» список
       - id: G01
         name: ...
    2) Обёртка
       groups:
         - id: G01
           name: ...
    """

    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    # Если внутри словарь с единственным ключом — берём его значение
    if isinstance(data, dict) and len(data) == 1:
        data = next(iter(data.values()))

    if not isinstance(data, list):
        raise ValueError(f"{path} должен содержать YAML-массив объектов "
                         "(лист элементов). Структура прочитана как: {type(data).__name__}")

    return data


def get_group_info(groups: list[dict], group_id: str) -> dict:
    """Извлекаем запись о группе по id."""

    for g in groups:
        if g["id"] == group_id:
            return g
    raise KeyError(f"Группа {group_id} не найдена в groups.yaml")


def get_errors_for_group(errors: list[dict], group: dict) -> list[dict]:
    """
    Возвращает ошибки, код которых присутствует в списке `group["codes"]`.
    Работает и для старой схемы (errors[].group_id) — на случай,
    если часть правил уже мигрирована.
    """
    codes = set(group.get("codes", []))

    filtered: list[dict] = []
    for err in errors:
        # 1) Новый способ — по списку кодов из groups.yaml
        if err.get("code") in codes:
            filtered.append(err)
            continue

        # 2) Ретрофит: вдруг всё-таки есть поле group_id
        if err.get("group_id") == group["id"]:
            filtered.append(err)

    return filtered

# ─────────────────────── Schema builder ──────────────────────────

def build_schema_classes(allowed_codes: list[str]):
    """Создаём динамический Literal и Pydantic‑классы под текущую группу."""

    # 1) Literal с разрешёнными кодами
    CodeLiteral = Literal[tuple(allowed_codes)]#type: ignore[arg‑type]

    # 2) Внутренний класс ErrorAnalysisDeep
    class ErrorAnalysisDeep(BaseModel):
        code: CodeLiteral
        process: ThoughtProcess
        verdict: Verdict
        instances: List[ErrorInstance]

    # 3) Финальный GroupReport
    class GroupReport(BaseModel):
        group_id: CodeLiteral | str  # чтоб всегда проходил id группы
        preliminary_notes: str = Field(..., description="Обзор ТЗ сквозь призму группы (≤120 слов)")
        errors: List[ErrorAnalysisDeep]
        overall_critique: Optional[str]

    return GroupReport

# ─────────────────────── Prompt builders ─────────────────────────

def build_system_prompt() -> str:
    """Системное сообщение (русский, статичное)."""

    return dedent(
        """
        Вы — старший технический аудитор российских технических заданий.
        Ваша задача — проанализировать входящий Markdown‑документ и вернуть
        ТОЛЬКО один валидный JSON‑объект по схеме GroupReport.
        Общие правила:
        • Работайте строго на русском языке.
        • Никакого текста вне JSON.
        • Для err_type="invalid" указывайте snippet, line_start, line_end, suggested_fix.
        • Для err_type="missing" эти поля не заполняйте.
        • Верните компактный JSON в одну строку.
        (Сама схема придёт в пользовательском сообщении.)
        """
    ).strip()


def build_user_prompt(
    schema_json: str,
    markdown_text: str,
    group: dict,
    errors: list[dict],
) -> str:
    """Собираем пользовательское сообщение по предложенному шаблону."""

    # Шаг‑за‑шагом инструкции (русифицированные)
    rules = dedent(
        """
        1. Найдите 1‑5 ключевых фрагментов текста → заполните массив "retrieval".
        2. Заполните "analysis": объясните, почему фрагмент нарушает критерий.
        3. Заполните "critique": укажите слабые места рассуждений.
        4. Заполните "verification": подтвердите/опровергните вывод.
        5. Для каждого кода ошибки сформируйте "instances":
           • err_type = "invalid" или "missing";
           • при "invalid" добавьте snippet, line_start, line_end, suggested_fix;
             при "missing" эти поля не заполняйте;
           • rationale — краткое обоснование.
        6. Если ошибка не обнаружена, verdict = "no_error", instances = [].
        7. Верните ОДНУ строку JSON без лишнего текста.
        """
    ).strip()

    # Формируем блок ошибок
    error_lines = []
    for err in errors:
        error_lines.append(
            f"{err['code']} — «{err['code']}»\n"
            f"Краткий критерий: {err['title']}\n"
            f"Полное описание: {err['description']}\n"
            f"Способ детекции: {err['detector']}\n"
        )
    errors_block = "\n".join(error_lines)

    user_prompt = dedent(
        f"""
        # === JSON‑схема ожидаемого ответа ===
        <SCHEMA>
        {schema_json}
        </SCHEMA>

        # === Алгоритм рассуждений ===
        {rules}

        # === Markdown‑документ для аудита ===
        <DOCUMENT>
        {markdown_text}
        </DOCUMENT>

        # === Контекст группы и ошибок ===
        <GROUP id=\"{group['id']}\">
        Название: {group['name']}
        Описание: {group['description']}

        <ERRORS>
        {errors_block}
        </ERRORS>
        </GROUP>

        # === Призыв к действию ===
        Проанализируйте документ по правилам выше и верните ТОЛЬКО валидный JSON.
        И ОЧЕНЬ ВАЖНО: верните _только_ валидный JSON, не добавляя никаких комментариев,
        обрезок «...» или описаний. Закройте все '{''}' и `[]`.
        """
    ).strip()

    return user_prompt

# ─────────────────────── LLM call via OpenRouter ─────────────────

def call_openrouter(model: str, sys_msg: str, usr_msg: str, api_key: str) -> str:
    """Отправляем ChatCompletion запрос к OpenRouter."""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": usr_msg},
        ],
        "temperature": 0,
        "max_tokens": 200_000,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

# ─────────────────────────── CLI glue ────────────────────────────

def main() -> None:
    """CLI‑входная точка."""

    parser = argparse.ArgumentParser(description="Проверка ТЗ на группу ошибок через LLM")
    parser.add_argument("--group", required=True, help="ID группы (например, G03)")
    parser.add_argument("--markdown", required=True, help="Путь к Markdown‑файлу")
    parser.add_argument(
        "--model", default="qwen/qwen3-235b-a22b-2507", help="ID модели OpenRouter"
    )
    args = parser.parse_args()

    api_key = os.getenv("OR_API_KEY")
    if not api_key:
        sys.exit("❌ Не задан OPENROUTER_API_KEY в переменных окружения")

    # Читаем YAML‑файлы
    try:
        groups = load_yaml(Path("groups.yaml"))
        errors = load_yaml(Path("errors.yaml"))
    except FileNotFoundError as exc:
        sys.exit(f"❌ {exc}")

    # Берём данные по группе / ошибкам
    group = get_group_info(groups, args.group)
    group_errors = get_errors_for_group(errors, group)
    if not group_errors:
        sys.exit(f"❌ Для группы {args.group} не найдено ни одной ошибки в errors.yaml")

    # Динамически создаём схемы с Literal‑ограничением
    GroupReport = build_schema_classes([e["code"] for e in group_errors])
    schema_json = json.dumps(GroupReport.model_json_schema(), ensure_ascii=False,indent=2,)

    # Читаем Markdown
    md_path = Path(args.markdown)
    if not md_path.exists():
        sys.exit(f"❌ Markdown‑файл {md_path} не найден")

    markdown_text = read_markdown(md_path)

    # Формируем промпты
    sys_prompt = build_system_prompt()
    usr_prompt = build_user_prompt(schema_json, markdown_text, group, group_errors)

    # Вызываем LLM
    print("▶️ Отправка запроса модели…", file=sys.stderr)
    try:
        llm_output = call_openrouter(args.model, sys_prompt, usr_prompt, api_key)
        print("RAW LLM OUTPUT:", llm_output, file=sys.stderr)
    except requests.HTTPError as exc:
        sys.exit(f"❌ Запрос не прошёл: {exc} — {exc.response.text}")

    # Валидируем JSON результата
    try:
        report = GroupReport.model_validate_json(llm_output)
    except (json.JSONDecodeError, ValidationError) as exc:
        sys.exit(f"❌ Ответ LLM невалидный: {exc}\nRAW: {llm_output[:500]}")

    # Выводим валидный JSON одной строкой
    report_dict = report.model_dump()
    pretty_json  = json.dumps(report_dict, ensure_ascii=False, indent=2)

    # 1) Сохраняем в файл для удобства чтения
    out_name = f"{md_path.stem}_{group['id']}_report.json"
    with open(out_name, "w", encoding="utf-8") as f:
        f.write(pretty_json)

    # 2) Печатаем компактный JSON в stdout (по старинке)
    print(json.dumps(report_dict, ensure_ascii=False, separators=(",", ":")))

    # Сообщаем пользователю, куда сохранили файл (опционально в stderr)
    print(f"✅ Отчёт сохранён в {out_name}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover
    main()
