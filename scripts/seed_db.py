#!/usr/bin/env python3
"""
scripts/seed_db.py

Заполняет таблицы error_groups и errors в PostgreSQL из YAML-файлов:
  - groups.yaml
  - errors.yaml

Как использовать:
    cd /path/to/project/root
    python scripts/seed_db.py
"""

import sys
from pathlib import Path

# Чтобы Python нашёл пакет tz_expert, добавляем корень проекта в sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import yaml
from tz_expert.db import engine, SessionLocal, Base
from tz_expert.models.orm import ErrorGroup, Error

def seed():
    # 1. Создать таблицы в БД (если их ещё нет)
    Base.metadata.create_all(bind=engine)
    
    session = SessionLocal()
    try:
        # 2. Загрузить группы из groups.yaml
        groups_data = yaml.safe_load(Path("groups.yaml").read_text(encoding="utf-8"))["groups"]
        for g in groups_data:
            # "G01" → 1, "G12" → 12
            gid = int(g["id"].lstrip("G"))
            grp = session.get(ErrorGroup, gid) or ErrorGroup(id=gid)
            grp.name               = g["name"]
            grp.group_description  = g.get("description", "")
            grp.is_deleted         = g.get("is_deleted", False)
            session.add(grp)
        session.commit()
        
        # 3. Загрузить ошибки из errors.yaml
        errors_data = yaml.safe_load(Path("errors.yaml").read_text(encoding="utf-8"))
        # Построить карту code → group_id
        code_to_group = {}
        for g in groups_data:
            gid = int(g["id"].lstrip("G"))
            for code in g.get("codes", []):
                code_to_group[code] = gid
        
        for r in errors_data:
            code = r["code"]
            err = session.query(Error).filter_by(code=code).first() or Error(code=code)
            err.name        = r["title"]
            err.description = r["description"]
            err.detector    = r["detector"]
            err.group_id    = code_to_group.get(code)
            session.add(err)
        session.commit()
        
        print("✅ Данные успешно загружены из YAML в Postgres.")
    except Exception as e:
        session.rollback()
        print("❌ Ошибка при сидировании:", e)
        raise
    finally:
        session.close()

if __name__ == "__main__":
    seed()
