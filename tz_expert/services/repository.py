# tz_expert/services/repository.py
from tz_expert.db import SessionLocal
from tz_expert.models.orm import ErrorGroup, Error

class RuleRepository:
    """Чистый доступ к таблицам errors и error_groups."""

    def __init__(self):
        self.session = SessionLocal()

    def get_all_rules(self) -> dict[str, dict]:
        """
        Возвращает словарь:
          { "E02": {"code":"E02","title":...,"description":...,"detector":...}, ... }
        """
        rows = self.session.query(Error).all()
        return {
            e.code: {
                "code": e.code,
                "title": e.name,
                "description": e.description,
                "detector": e.detector
            }
            for e in rows
        }

    def get_all_groups(self) -> dict[str, dict]:
        """
        Возвращает словарь:
          { "G01": {"id":"G01","name":...,"system_prompt":"", "codes":["E01A","E01B"]}, ... }
        Мы берем id как строку "G01", name, и составляем список кодов из связанных ошибок.
        """
        rows = self.session.query(ErrorGroup).filter_by(is_deleted=False).all()
        result = {}
        for g in rows:
            # приводим id к тому же виду, что и раньше: "G01"
            gid = f"G{g.id:02d}"
            result[gid] = {
                "id": gid,
                "name": g.name,
                "system_prompt": g.group_description or "",     # если нужно, можно хранить в БД или читать из файлов later
                "codes": [e.code for e in g.errors]
            }
        return result

    def close(self):
        self.session.close()
