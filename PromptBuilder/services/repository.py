"""Read-only DB access layer for PromptBuilder."""
from contextlib import contextmanager
from typing import Iterable, List, Dict, Any, Optional

from sqlalchemy.orm import joinedload

from PromptBuilder.core.db import SessionLocal
from PromptBuilder.models.orm import ErrorGroup, Error, ErrorGroupGroup


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
        """Return group metadata for a given GG."""
        with _session_scope() as s:
            rows = (
                s.query(ErrorGroup)
                 .options(joinedload(ErrorGroup.errors))
                 .filter(ErrorGroup.is_deleted.is_(False))
                 .filter(ErrorGroup.gg_id == gg_id)
                 .all()
            )
            # Sort groups by code (fallback to name); errors by code for stable prompts
            rows = sorted(rows, key=lambda g: (g.code or g.name or ""))
            out: List[Dict] = []
            for g in rows:
                error_ids = sorted(e.id for e in g.errors)
                error_codes = sorted(e.code for e in g.errors)
                out.append(
                    {
                        "group_id": g.id,
                        "group_code": g.code,
                        "group_name": g.name,
                        "group_description": g.group_description or "",
                        "error_ids": error_ids,
                        "error_codes": error_codes,
                    }
                )
            return out

    def get_latest_gg_full(self) -> Optional[Dict[str, Any]]:
        """Return the latest GG (by id) with groups and errors."""
        with _session_scope() as s:
            gg_row: Optional[ErrorGroupGroup] = (
                s.query(ErrorGroupGroup)
                 .order_by(ErrorGroupGroup.id.desc())
                 .first()
            )
            if not gg_row:
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

            return {
                "ggid": gg_row.id,
                "gg": {"id": gg_row.id, "name": gg_row.name},
                "groups": out_groups,
            }

    def get_gg_full(self, gg_id: int) -> Optional[Dict[str, Any]]:
        """Same as get_latest_gg_full but for a specific gg_id."""
        with _session_scope() as s:
            gg_row: Optional[ErrorGroupGroup] = s.get(ErrorGroupGroup, gg_id)
            if not gg_row:
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

            return {
                "ggid": gg_row.id,
                "gg": {"id": gg_row.id, "name": gg_row.name},
                "groups": out_groups,
            }

    def create_gg(self, *, gg: Dict[str, Any], groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a new GG with nested groups/errors (for admin tooling)."""
        with _session_scope() as s:
            gg_name = gg.get("name")
            if not gg_name:
                raise ValueError("gg.name is required")
            gg_row = ErrorGroupGroup(name=gg_name)
            s.add(gg_row)
            s.flush()  # obtain gg_row.id

            for g in groups:
                g_row = ErrorGroup(
                    name=g.get("name"),
                    code=g.get("code"),
                    group_description=g.get("groupDescription"),
                    is_deleted=bool(g.get("isDeleted", False)),
                    gg_id=gg_row.id,
                )
                s.add(g_row)
                s.flush()

                for e in g.get("errors", []) or []:
                    e_row = Error(
                        code=e.get("code"),
                        name=e.get("name"),
                        description=e.get("description"),
                        detector=e.get("detector"),
                        group_id=g_row.id,
                    )
                    s.add(e_row)

        created = self.get_latest_gg_full()
        assert created is not None
        return created

    def get_rules_by_ids(self, ids: Iterable[int]) -> List[Dict]:
        """Fetch error metadata by IDs for prompt construction."""
        ids = list(ids)
        if not ids:
            return []
        with _session_scope() as s:
            rows = s.query(Error).filter(Error.id.in_(ids)).all()
            rows = sorted(rows, key=lambda r: r.code)
            return [
                {
                    "id": r.id,
                    "code": r.code,
                    "title": r.name,
                    "description": r.description,
                    "detector": r.detector,
                }
                for r in rows
            ]
