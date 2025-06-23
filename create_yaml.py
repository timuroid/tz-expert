"""
make_errors_yaml.py
~~~~~~~~~~~~~~~~~~~
Скрипт формирует YAML-файл с описанием ошибок для LLM-сервиса.

Вход:  Excel-файл `списокошибок.xlsx`, лист №1
       - «Код»                        → code
       - «Критерий оценки»            → title
       - «Упрощённый критерий оценки» → description
       - «Описание критерия оценки»   → detector
       - «Тип триггера»               → kind

Выход: файл `errors.yaml`
"""

from pathlib import Path           # Работа с путями к файлам
import pandas as pd                # Чтение Excel
from ruamel.yaml import YAML       # Запись YAML c красивым форматированием

# ---------- Параметры ----------
XLSX_PATH = Path("errors_list.xlsx")   # Excel-файл с таблицей
YAML_PATH = Path("errors.yaml")         # Итоговый YAML

# ---------- Чтение Excel ----------
# read_excel возвращает DataFrame; по умолчанию берём первый лист
df = pd.read_excel(XLSX_PATH)

# Убедимся, что названия колонок точно совпадают с тем, что в файле
expected_cols = [
    "Код",
    "Критерий оценки",
    "Упрощённый критерий оценки",
    "Описание критерия оценки",
    "Тип триггера",
]
missing = set(expected_cols) - set(df.columns)
if missing:
    raise ValueError(
        f"В Excel не найдены столбцы: {', '.join(missing)}\n"
        "Проверьте названия или укажите правильные."
    )

# ---------- Подготовка данных ----------
# Переименуем колонки сразу «как нужно» для YAML
df = df.rename(
    columns={
        "Код": "code",
        "Критерий оценки": "title",
        "Упрощённый критерий оценки": "description",
        "Описание критерия оценки": "detector",
        "Тип триггера": "kind",
    }
)

# Приведём kind к строгим значениям: Invalid | both
df["kind"] = (
    df["kind"]
    .astype(str)
    .str.strip()
    .str.capitalize()          # invalid → Invalid, both → Both
)
df.loc[~df["kind"].isin(["Invalid", "Both"]), "kind"] = "Invalid"  # fallback

# ---------- Запись YAML ----------
yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)   # Красивые отступы
yaml.default_flow_style = False                # Многострочный формат

with YAML_PATH.open("w", encoding="utf-8") as f:
    # DataFrame -> list[dict], чтобы YAML знал порядок полей
    records = df[["code", "title", "description", "detector", "kind"]].to_dict("records")
    yaml.dump(records, f)

print(f"✅ Файл {YAML_PATH} создан: {len(records)} ошибок экспортировано.")
