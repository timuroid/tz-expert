"""Маршруты TzeExpert."""
from __future__ import annotations

from fastapi import APIRouter, Body

from TzeExpert.schemas import JobRequest, JobResponse
from TzeExpert.services.pipeline import TzeExpertService


router = APIRouter(prefix="/v1/tze-expert", tags=["TzeExpert"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analyze", response_model=JobResponse, summary="Запустить двухшаговый аудит требований")
async def analyze(req: JobRequest = Body(...)) -> JobResponse:
    service = TzeExpertService()
    return await service.run(req)

