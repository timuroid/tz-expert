"""
app/routers.py
HTTP-роуты PromptBuilder.

Изменения:
- убрана meta из ответа;
- ggid и schema на корневом уровне.
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from PromptBuilder.schemas import (
    BuildRequest,
    BuildResponse,
    LatestGGResponse,
    CreateGGRequest,
)
from PromptBuilder.services.builder import PromptBuilderService
from PromptBuilder.services.repository import Repo

router = APIRouter(prefix="/v1/prompt-builder", tags=["PromptBuilder"])

def get_repo() -> Repo:
    """DI: новый Repo на каждый запрос."""
    return Repo()

@router.post("/build", response_model=BuildResponse, summary="Собрать messages по markdown+gg_id")
def build(req: BuildRequest = Body(...), repo: Repo = Depends(get_repo)):
    svc = PromptBuilderService(repo)
    items = svc.build_items(markdown=req.markdown, gg_id=req.ggid)
    schema = svc.output_schema()
    # Полная информация по указанной группе-группе (как latest-gg)
    gg_full = repo.get_gg_full(req.ggid)
    gg_meta = gg_full.get("gg") if gg_full else None
    gg_groups = gg_full.get("groups") if gg_full else None
    return BuildResponse(ggid=req.ggid, items=items, schema_=schema, gg=gg_meta, groups=gg_groups)


@router.get("/latest-gg", response_model=LatestGGResponse, summary="Получить самый свежий GG с группами и ошибками")
def latest_gg(repo: Repo = Depends(get_repo)):
    data = repo.get_latest_gg_full()
    if not data:
        raise HTTPException(status_code=404, detail="Нет записей GG")
    return LatestGGResponse(**data)


@router.post("/gg", status_code=status.HTTP_201_CREATED, summary="Создать новый GG с группами и ошибками")
def create_gg(req: CreateGGRequest = Body(...), repo: Repo = Depends(get_repo)):
    created = repo.create_gg(
        gg=req.gg,
        groups=[g.model_dump() for g in req.groups],
    )
    # Возвращаем только код 201 без тела, как просили
    return Response(status_code=status.HTTP_201_CREATED)
