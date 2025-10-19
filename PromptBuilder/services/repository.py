"""Read-only DB access layer for PromptBuilder."""
from contextlib import contextmanager
from typing import Iterable, List, Dict, Any, Optional

from sqlalchemy.orm import joinedload

from PromptBuilder.core.db import SessionLocal
from PromptBuilder.models.orm import ErrorGroup, Error, ErrorGroupGroup
import logging


@contextmanager
def _session_scope():
    """Контекст менеджер сессии SQLAlchemy.

    Обеспечивает закрытие сессии и rollback при исключении. Коммит выполняется
    в конце блока. Методы репозитория используют этот контекст только для чтения,
    но подход остаётся единообразным.
    """
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
    """Read‑only репозиторий для доступа к каталогу групп/правил в БД.

    Методы репозитория возвращают простые словари/списки, удобные для шаблонов
    и сборки промптов. Запись/админ‑операции удалены.
    """

    def __init__(self) -> None:
        self._log = logging.getLogger(__name__)
    def get_groups_by_ggid(self, gg_id: int) -> List[Dict]:
        """Вернуть метаданные групп для заданного каталога GG."""
        with _session_scope() as s:
            self._log.debug("repo: get_groups_by_ggid(ggid=%s)", gg_id)
            rows = (
                s.query(ErrorGroup)
                 .options(joinedload(ErrorGroup.errors))
                 .filter(ErrorGroup.is_deleted.is_(False))
                 .filter(ErrorGroup.gg_id == gg_id)
                 .all()
            )
            # Sort groups by code (fallback to name)
            rows = sorted(rows, key=lambda g: (g.code or g.name or ""))
            out: List[Dict] = []
            for g in rows:
                error_ids = sorted(e.id for e in g.errors)
                out.append(
                    {
                        "group_id": g.id,
                        "group_code": g.code,
                        "group_name": g.name,
                        "group_description": g.group_description or "",
                        "error_ids": error_ids,
                    }
                )
            self._log.info("repo: groups=%s (ggid=%s)", len(out), gg_id)
            return out

    # get_latest_gg_full removed (legacy/admin)

    def get_gg_full(self, gg_id: int) -> Optional[Dict[str, Any]]:
        """Вернуть полный каталог GG с группами и ошибками по `gg_id`."""
        with _session_scope() as s:
            self._log.debug("repo: get_gg_full(ggid=%s)", gg_id)
            gg_row: Optional[ErrorGroupGroup] = s.get(ErrorGroupGroup, gg_id)
            if not gg_row:
                self._log.info("repo: gg not found (ggid=%s)", gg_id)
                return None

            groups: List[ErrorGroup] = (
                s.query(ErrorGroup)
                 .options(joinedload(ErrorGroup.errors))
                 .filter(ErrorGroup.gg_id == gg_row.id)
                 .all()
            )
            groups_sorted = sorted(groups, key=lambda g: (g.code or g.name or ""))

            out_groups: List[Dict[str, Any]] = []
            for g in groups_sorted:
                errors_sorted = sorted(g.errors, key=lambda e: (e.code or ""))
                out_groups.append(
                    {
                        "id": g.id,
                        "name": g.name,
                        "code": g.code,
                        "groupDescription": g.group_description or "",
                        "isDeleted": bool(g.is_deleted),
                        "errors": [
                            {
                                "id": e.id,
                                "code": e.code,
                                "name": e.name,
                                "description": e.description,
                                "detector": e.detector,
                            }
                            for e in errors_sorted
                        ],
                    }
                )

            result = {
                "ggid": gg_row.id,
                "gg": {"id": gg_row.id, "name": gg_row.name},
                "groups": out_groups,
            }
            self._log.info("repo: gg_full ready (ggid=%s, groups=%s)", gg_id, len(out_groups))
            return result

    # Removed: create_gg (admin tooling)

    def get_rules_by_ids(self, ids: Iterable[int]) -> List[Dict]:
        """Получить метаданные правил по их ID (для вставки в промпт)."""
        ids = list(ids)
        if not ids:
            return []
        with _session_scope() as s:
            self._log.debug("repo: get_rules_by_ids(ids=%s)", list(ids))
            rows = s.query(Error).filter(Error.id.in_(ids)).all()
            rows = sorted(rows, key=lambda r: r.code)
            result = [
                {
                    "id": r.id,
                    "code": r.code,
                    "title": r.name,
                    "description": r.description,
                    "detector": r.detector,
                }
                for r in rows
            ]
            self._log.info("repo: fetched rules=%s", len(result))
            return result
