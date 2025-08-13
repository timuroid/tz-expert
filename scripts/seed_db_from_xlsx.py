#!/usr/bin/env python3
"""
scripts/seed_db_from_xlsx.py
----------------------------------

⚙️ Назначение
=============
Заполняет таблицы *error_groups* и *errors* в PostgreSQL из:
• YAML-файла groups.yaml (описания групп ошибок);
• Excel-файла со списком ошибок.

Дополнительно:
• Гарантированно создаёт супергруппу в таблице *error_group_groups* с id=1
  и именем «Главная группа» (без FK).
• Присваивает всем записям в *error_groups* значение gg_id = 1.

Запуск
------
    cd /path/to/project/root
    python scripts/seed_db_from_xlsx.py [путь_к_xlsx]

Требования
----------
pip install pandas openpyxl pyyaml sqlalchemy
"""

import sys
from pathlib import Path
from typing import Dict, Any, List

# ──────────────────────────────────────────────────────────────
# Подготовка окружения (чтобы импортировать tz_expert.*)
# ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))  # добавляем корень проекта в PYTHONPATH

# ──────────────────────────────────────────────────────────────
# Внешние зависимости
# ──────────────────────────────────────────────────────────────
import yaml                   # работа с groups.yaml
import pandas as pd           # чтение Excel
from sqlalchemy import text   # безопасные SQL с параметрами
from sqlalchemy.exc import SQLAlchemyError

# ──────────────────────────────────────────────────────────────
# Внутренние модули проекта (ORM, движок БД)
# ──────────────────────────────────────────────────────────────
from tz_expert.db import engine, SessionLocal, Base
from tz_expert.models.orm import ErrorGroup, Error


# --------------------------- Константы --------------------------- #

#: Путь к YAML с группами (относительно корня проекта)
GROUPS_YAML_PATH = PROJECT_ROOT / "groups.yaml"

#: Путь к Excel (можно переопределить первым аргументом CLI)
DEFAULT_XLSX_PATH = PROJECT_ROOT / "sgr_results.xlsx"

#: Имя листа с данными
SHEET_NAME = "итоговый лист"

#: Соответствие «Название столбца в Excel» → «ключ в ORM»
COLUMN_MAP = {
    "Код": "code",
    "Название": "title",
    "Описание ": "description",
    "Способ детекции": "detector",
}

# --------------------------- Хелперы --------------------------- #

def ensure_main_supergroup(session) -> int:
    """
    Гарантирует наличие супергруппы в таблице error_group_groups.
    Создаёт запись с id=1 и name='Главная группа', если её нет.
    Возвращает id супергруппы (всегда 1).
    """
    # idempotent-вставка: если запись с id=1 уже существует — просто обновим имя
    session.execute(
        text("""
            INSERT INTO error_group_groups (id, name)
            VALUES (:id, :name)
            ON CONFLICT (id) DO UPDATE
            SET name = EXCLUDED.name
        """),
        {"id": 1, "name": "Главная группа"},
    )
    # flush — чтобы вставка попала в транзакцию до последующих апдейтов
    session.flush()
    return 1


def set_all_groups_ggid(session, supergroup_id: int) -> None:
    """
    Проставляет всем строкам в error_groups значение gg_id = supergroup_id.
    Делается сырой SQL, чтобы не зависеть от версии ORM-модели.
    """
    session.execute(text("UPDATE error_groups SET gg_id = :sid"), {"sid": supergroup_id})
    session.flush()


# --------------------------- Функции --------------------------- #

def load_groups(session) -> Dict[str, int]:
    """
    Загружает группы из groups.yaml в БД и возвращает
    словарь «код_ошибки → id_группы», сформированный на основе
    раздела *codes* внутри YAML.
    """
    # ① Читаем YAML
    groups_raw: List[Dict[str, Any]] = yaml.safe_load(
        GROUPS_YAML_PATH.read_text(encoding="utf-8")
    )["groups"]

    # ② Сохраняем / обновляем группы в БД
    for g in groups_raw:
        gid = int(g["id"].lstrip("G"))             # "G03" → 3
        grp = session.get(ErrorGroup, gid) or ErrorGroup(id=gid)  # upsert по PK
        grp.name = g["name"]
        grp.group_description = g.get("description", "")
        grp.is_deleted = g.get("is_deleted", False)
        session.add(grp)
    session.flush()  # фиксируем id-ы в рамках транзакции

    # ③ Строим mapping «код_ошибки → id_группы»
    code_to_group: Dict[str, int] = {}
    for g in groups_raw:
        gid = int(g["id"].lstrip("G"))
        for code in g.get("codes", []):
            code_to_group[code] = gid
    return code_to_group


def excel_to_records(xlsx_path: Path) -> List[Dict[str, Any]]:
    """
    Читает Excel и приводит строки к формату,
    совместимому с ORM `Error`.
    """
    # ① Загружаем лист в DataFrame
    df: pd.DataFrame = pd.read_excel(
        xlsx_path,
        sheet_name=SHEET_NAME,
        dtype=str,         # читаем всё строками → меньше сюрпризов
        engine="openpyxl",
    ).fillna("")           # пустые ячейки → ""

    # ② Переименовываем колонки + отбираем только нужные
    df = df[list(COLUMN_MAP.keys())].rename(columns=COLUMN_MAP)

    # ③ Преобразуем в список dict-ов
    return df.to_dict(orient="records")


def seed(xlsx_path: Path = DEFAULT_XLSX_PATH) -> None:
    """
    Основная точка входа: заливает группы и ошибки в БД
    + создаёт супергруппу (id=1, «Главная группа»)
    + проставляет gg_id=1 для всех error_groups.
    """
    # ① Создаём таблицы, если их ещё нет (по описанию ORM-моделей)
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        # ② Гарантируем супергруппу (id=1)
        main_gid = ensure_main_supergroup(session)  # → 1

        # ③ Загружаем/обновляем группы из YAML
        code_to_group = load_groups(session)

        # ④ Всем группам ошибок проставляем gg_id = 1
        set_all_groups_ggid(session, main_gid)

        # ⑤ Загружаем ошибки из Excel
        error_records = excel_to_records(xlsx_path)
        for rec in error_records:
            code = rec["code"]
            # upsert по коду
            err: Error = (
                session.query(Error).filter_by(code=code).first() or Error(code=code)
            )
            err.name = rec["title"]
            err.description = rec["description"]
            err.detector = rec["detector"]
            err.group_id = code_to_group.get(code)  # может быть None, если код не найден
            session.add(err)

        # ⑥ Коммитим все изменения одной транзакцией
        session.commit()
        print(f"✅ Данные загружены. Супергруппа id={main_gid} ('Главная группа'), gg_id у всех групп = {main_gid}.")
    except (FileNotFoundError, SQLAlchemyError, KeyError, ValueError) as exc:
        session.rollback()
        print("❌ Ошибка при сидировании:", exc)
        raise
    finally:
        session.close()


# --------------------------- Точка входа --------------------------- #

if __name__ == "__main__":
    # Позволяем указать путь к Excel первым аргументом CLI
    xlsx_cli_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX_PATH
    seed(xlsx_cli_path)
