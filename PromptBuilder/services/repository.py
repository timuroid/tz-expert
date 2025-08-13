"""
Только чтение БД для PromptBuilder.
"""
from contextlib import contextmanager
from typing import Iterable, List, Dict
from sqlalchemy.orm import joinedload

from PromptBuilder.core.db import SessionLocal
from PromptBuilder.models.orm import ErrorGroup, Error

@contextmanager
def _session_scope():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()

class Repo:
    def get_groups_by_ggid(self, gg_id: int) -> List[Dict]:
        """Возвращает данные групп внутри gg_id."""
        with _session_scope() as s:
            rows = (
                s.query(ErrorGroup)
                 .options(joinedload(ErrorGroup.errors))
                 .filter(ErrorGroup.is_deleted.is_(False))
                 .filter(ErrorGroup.gg_id == gg_id)
                 .all()
            )
            out: List[Dict] = []
            for g in rows:
                error_ids = sorted(e.id for e in g.errors)
                error_codes = sorted(e.code for e in g.errors)  # для текста промпта может пригодиться
                out.append({
                    "group_id": g.id,                          # int
                    "group_code": f"G{g.id:02d}",              # "G07"
                    "group_description": g.group_description or "",
                    "error_ids": error_ids,                    # список ID
                    "error_codes": error_codes,                # список кодов (E01…)
                })
            return out

    def get_rules_by_ids(self, ids: Iterable[int]) -> List[Dict]:
        """Детали ошибок для текста промпта по ID."""
        ids = list(ids)
        if not ids:
            return []
        with _session_scope() as s:
            rows = s.query(Error).filter(Error.id.in_(ids)).all()
            rows = sorted(rows, key=lambda r: r.code)
            return [{
                "id": r.id,
                "code": r.code,
                "title": r.name,
                "description": r.description,
                "detector": r.detector,
            } for r in rows]
