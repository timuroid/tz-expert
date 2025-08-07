#!/usr/bin/env python3
"""
scripts/seed_db_from_xlsx.py
----------------------------------

⚙️ Назначение
=============
Заполняет таблицы *error_groups* и *errors* в PostgreSQL:

• **Группы ошибок** берутся из YAML-файла *groups.yaml* (как в оригинальном seed).  
• **Ошибки** читаются из Excel-книги *Список ошибок.xlsx* (лист «Лист1»).

Запуск
------
    cd /path/to/project/root
    python scripts/seed_db_from_xlsx.py

Требования
----------
pip install pandas openpyxl pyyaml sqlalchemy

Аргументы командной строки
--------------------------
– Без аргументов             → использует файлы по умолчанию.  
– 1-й аргумент = путь к xlsx → `python seed_db_from_xlsx.py path/to/file.xlsx`.

Автор
-----
TzExpert / LLM-сервис проверки ТЗ
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
import yaml           # работа с groups.yaml
import pandas as pd   # чтение Excel
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

# --------------------------- Функции --------------------------- #


def load_groups(session) -> Dict[str, int]:
    """
    Загружает группы из groups.yaml в БД и возвращает
    словарь «код_ошибки → id_группы», сформированный на основе
    раздела *codes* внутри YAML.

    Args:
        session (Session): открытая сессия SQLAlchemy

    Returns:
        Dict[str, int]: mapping «E01A → 1»
    """
    # ① Читаем YAML
    groups_raw: List[Dict[str, Any]] = yaml.safe_load(
        GROUPS_YAML_PATH.read_text(encoding="utf-8")
    )["groups"]

    # ② Сохраняем / обновляем группы в БД
    for g in groups_raw:
        gid = int(g["id"].lstrip("G"))          # "G03" → 3
        grp = session.get(ErrorGroup, gid) or ErrorGroup(id=gid)
        grp.name = g["name"]
        grp.group_description = g.get("description", "")
        grp.is_deleted = g.get("is_deleted", False)
        session.add(grp)                        # upsert
    session.flush()  # fix id-ы сразу, но без commit

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

    Args:
        xlsx_path (Path): путь к книге Excel

    Returns:
        List[Dict[str, Any]]: 
            [{'code': 'E01A', 'title': '...', 'description': '...', 'detector': 'Invalid'}, …]
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
    Основная точка входа: заливает группы и ошибки в БД.

    Args:
        xlsx_path (Path, optional): Excel с ошибками. По умолчанию DEFAULT_XLSX_PATH.
    """
    # ① Создаём таблицы, если их ещё нет
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        # ② ───────── загрузка групп ─────────
        code_to_group = load_groups(session)

        # ③ ───────── загрузка ошибок ─────────
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

        # ④ Коммитим все изменения одной транзакцией
        session.commit()
        print(f"✅ Данные из «{xlsx_path.name}» загружены в Postgres.")
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
