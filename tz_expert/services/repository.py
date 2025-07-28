# tz_expert/services/repository.py
"""
Repository: чистый доступ к таблицам error_groups / errors
Каждый метод открывает свою Session, ⇒ нет «висящих» транзакций.
"""

from contextlib import contextmanager
from tz_expert.db import SessionLocal
from tz_expert.models.orm import ErrorGroup, Error


@contextmanager
def _session_scope():
    """Контекст-менеджер «безопасная сессия»."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:          # любая SQL-ошибка
        session.rollback()
        raise
    finally:
        session.close()


class RuleRepository:
    """Статeless-класс: ни одной долгоживущей Session внутри."""

    # ---------- ERRORS ----------
    def get_all_rules(self) -> dict[str, dict]:
        with _session_scope() as s:
            rows = s.query(Error).all()
            return {
                e.code: {
                    "code":        e.code,
                    "title":       e.name,
                    "description": e.description,
                    "detector":    e.detector,
                }
                for e in rows
            }

    # ---------- GROUPS ----------
    def get_all_groups(self) -> dict[str, dict]:
        with _session_scope() as s:
            rows = (
                s.query(ErrorGroup)
                .filter_by(is_deleted=False)
                .all()
            )
            result: dict[str, dict] = {}
            for g in rows:
                gid = f"G{g.id:02d}"                 # "G01"
                result[gid] = {
                    "id":            gid,
                    "name":          g.name,
                    "system_prompt": g.group_description or "",
                    "codes":         [e.code for e in g.errors],
                }
            return result

