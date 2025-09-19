"""PromptBuilder HTTP endpoints."""
from fastapi import APIRouter, Body, Depends, HTTPException, Response, status

from PromptBuilder.schemas import (
    BuildRequest,
    BuildResponse,
    CreateGGRequest,
    LatestGGResponse,
    Step1BuildRequest,
    Step1BuildResponse,
    Step2BuildRequest,
    Step2BuildResponse,
)
from PromptBuilder.services.builder import PromptBuilderService
from PromptBuilder.services.repository import Repo

router = APIRouter(prefix="/v1/prompt-builder", tags=["PromptBuilder"])


def get_repo() -> Repo:
    """Simple DI helper returning a fresh repo instance."""
    return Repo()


@router.post("/build", response_model=BuildResponse, summary="Совместимость: промпты шага 1 по всем группам")
def build(req: BuildRequest = Body(...), repo: Repo = Depends(get_repo)):
    svc = PromptBuilderService(repo)
    items = svc.build_items(markdown=req.markdown, gg_id=req.ggid)
    schema = svc.output_schema()
    gg_full = repo.get_gg_full(req.ggid)
    gg_meta = gg_full.get("gg") if gg_full else None
    gg_groups = gg_full.get("groups") if gg_full else None
    return BuildResponse(ggid=req.ggid, items=items, schema_=schema, gg=gg_meta, groups=gg_groups)


@router.post("/step1/build", response_model=Step1BuildResponse, summary="Шаг 1: промпты по группам ошибок")
def build_step1(req: Step1BuildRequest = Body(...), repo: Repo = Depends(get_repo)):
    svc = PromptBuilderService(repo)
    return svc.build_step1_response(req)


@router.post("/step2/build", response_model=Step2BuildResponse, summary="Шаг 2: промпт для отчёта по разделам")
def build_step2(req: Step2BuildRequest = Body(...)):
    svc = PromptBuilderService()
    return svc.build_step2_prompt(req)


@router.get("/latest-gg", response_model=LatestGGResponse, summary="Последний классификатор групп и ошибок")
def latest_gg(repo: Repo = Depends(get_repo)):
    data = repo.get_latest_gg_full()
    if not data:
        raise HTTPException(status_code=404, detail="Нет действующего классификатора")
    return LatestGGResponse(**data)


@router.post("/gg", status_code=status.HTTP_201_CREATED, summary="Создать новый классификатор (админ)")
def create_gg(req: CreateGGRequest = Body(...), repo: Repo = Depends(get_repo)):
    repo.create_gg(
        gg=req.gg,
        groups=[g.model_dump() for g in req.groups],
    )
    return Response(status_code=status.HTTP_201_CREATED)
