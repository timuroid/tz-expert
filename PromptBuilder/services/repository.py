"""
services/repository.py
Только чтение БД для PromptBuilder.
"""
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
        """Возвращает данные групп внутри gg_id."""
        with _session_scope() as s:
            rows = (
                s.query(ErrorGroup)
                 .options(joinedload(ErrorGroup.errors))
                 .filter(ErrorGroup.is_deleted.is_(False))
                 .filter(ErrorGroup.gg_id == gg_id)
                 .all()
            )
            # сортировка групп по code (если есть) иначе по name; ошибки по коду (e01a, e01b, ...)
            rows = sorted(rows, key=lambda g: (g.code or g.name or ""))
            out: List[Dict] = []
            for g in rows:
                error_ids = sorted(e.id for e in g.errors)
                error_codes = sorted(e.code for e in g.errors)  # для текста промпта может пригодиться
                out.append({
                    "group_id": g.id,                          # int
                    "group_code": g.code,        # используем сохранённый код
                    "group_name": g.name,
                    "group_description": g.group_description or "",
                    "error_ids": error_ids,                    # список ID
                    "error_codes": error_codes,                # список кодов (E01…)
                })
            return out

    def get_latest_gg_full(self) -> Optional[Dict[str, Any]]:
        """Возвращает самый свежий GG (max id) со списком групп и ошибок в требуемой структуре.

        Структура: { ggid, gg: {id,name}, groups: [{id,name,groupDescription,isDeleted,errors:[...] }]}.
        Группы сортируем по name, ошибки по code.
        """
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
                out_groups.append({
                    "id": g.id,
                    "name": g.name,
                    "code": g.code,
                    "groupDescription": g.group_description or "",
                    "isDeleted": bool(g.is_deleted),
                    "errors": [{
                        "id": e.id,
                        "code": e.code,
                        "name": e.name,
                        "description": e.description,
                        "detector": e.detector,
                    } for e in errors_sorted]
                })

            return {
                "ggid": gg_row.id,
                "gg": {"id": gg_row.id, "name": gg_row.name},
                "groups": out_groups,
            }

    def get_gg_full(self, gg_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает GG с указанным id со списком групп и ошибок в той же структуре, что и latest.

        Структура: { ggid, gg: {id,name}, groups: [{id,name,code,groupDescription,isDeleted,errors:[...] }]}.
        Группы сортируем по code (если есть) иначе по name, ошибки по code.
        """
        with _session_scope() as s:
            gg_row: Optional[ErrorGroupGroup] = s.query(ErrorGroupGroup).get(gg_id)  # type: ignore[arg-type]
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
                out_groups.append({
                    "id": g.id,
                    "name": g.name,
                    "code": g.code,
                    "groupDescription": g.group_description or "",
                    "isDeleted": bool(g.is_deleted),
                    "errors": [{
                        "id": e.id,
                        "code": e.code,
                        "name": e.name,
                        "description": e.description,
                        "detector": e.detector,
                    } for e in errors_sorted]
                })

            return {
                "ggid": gg_row.id,
                "gg": {"id": gg_row.id, "name": gg_row.name},
                "groups": out_groups,
            }

    def create_gg(self, *, gg: Dict[str, Any], groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Создать новый GG (error_group_groups) с вложенными группами и ошибками.

        Ожидаемые ключи:
          gg: { name }
          groups: [ { name, groupDescription, isDeleted, errors: [ { code, name, description, detector } ] } ]
        Возвращает созданный объект в формате get_latest_gg_full().
        """
        with _session_scope() as s:
            # 1) GG
            gg_name = gg.get("name")
            if not gg_name:
                raise ValueError("gg.name is required")
            gg_row = ErrorGroupGroup(name=gg_name)
            s.add(gg_row)
            s.flush()  # получить gg_row.id

            # 2) Groups
            for g in groups:
                g_row = ErrorGroup(
                    name=g.get("name"),
                    code=g.get("code"),  # используем сохранённый код
                    group_description=g.get("groupDescription"),
                    is_deleted=bool(g.get("isDeleted", False)),
                    gg_id=gg_row.id,
                )
                s.add(g_row)
                s.flush()

                # 3) Errors
                for e in g.get("errors", []) or []:
                    e_row = Error(
                        code=e.get("code"),
                        name=e.get("name"),
                        description=e.get("description"),
                        detector=e.get("detector"),
                        group_id=g_row.id,
                    )
                    s.add(e_row)

        # Возврат свежесозданного объекта тем же методом
        created = self.get_latest_gg_full()
        assert created is not None
        return created

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
