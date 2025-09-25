"""Маршруты TzeExpert."""
from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, Body

from PromptBuilder.analysis_schemas import FinalReportBySections
from TzeExpert.schemas import (
    JobRequest,
    JobResponse,
    ReportFromResponseRequest,
    ReportFromResponseResponse,
)
from TzeExpert.services.pipeline import TzeExpertService
from TzeExpert.services.report_docx import write_final_report_docx


router = APIRouter(prefix="/v1/tze-expert", tags=["TzeExpert"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analyze", response_model=JobResponse, summary="Запустить двухшаговый аудит требований")
async def analyze(req: JobRequest = Body(...)) -> JobResponse:
    service = TzeExpertService()
    return await service.run(req)


@router.post(
    "/report-from-llmresponse",
    response_model=ReportFromResponseResponse,
    summary="Сгенерировать DOCX по полному JSON-ответу LLM",
)
async def report_from_llmresponse(
    req: ReportFromResponseRequest = Body(...),
) -> ReportFromResponseResponse:
    """Принять полный JSON-ответ и построить DOCX.

    Поддерживаемые формы:
    - {status, url, result: RunResponse}
    - RunResponse (result/usage/cost/model_uri/attempts)
    - Непосредственно итоговый отчёт (doc_title, document_wide, by_sections)
    """

    obj = req.envelope

    # Разворачиваем сохранённый конверт {status,url,result}
    if isinstance(obj, dict) and {"status", "url", "result"}.issubset(set(obj.keys())):
        obj = obj.get("result")

    # Разворачиваем ответ вида RunResponse
    if isinstance(obj, dict) and {"result", "usage"}.issubset(set(obj.keys())):
        inner = obj.get("result")
        if isinstance(inner, str):
            try:
                inner = json.loads(inner)
            except Exception:
                pass
        obj = inner

    # Если это строка JSON
    if isinstance(obj, str):
        obj = json.loads(obj)

    # Нормализуем возможные старые ключи + добавим пустые списки по умолчанию
    if isinstance(obj, dict):
        if "by_sections" not in obj and "y_sections" in obj:
            obj["by_sections"] = obj.pop("y_sections")
        if "document_wide" not in obj and "document_wide_errors" in obj:
            obj["document_wide"] = obj.pop("document_wide_errors")
        # требуемые ключи в схеме шага 2: добавим [] если отсутствуют
        obj.setdefault("document_wide", [])
        obj.setdefault("by_sections", [])

    report = FinalReportBySections.model_validate(obj)
    run_id = req.run_id or uuid4().hex
    out_path = write_final_report_docx(report, run_id=run_id, ggid=req.ggid)

    return ReportFromResponseResponse(path=str(out_path), report=report)
