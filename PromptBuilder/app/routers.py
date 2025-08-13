"""
HTTP-роуты PromptBuilder.

Изменения:
- убрана meta из ответа;
- ggid и schema на корневом уровне.
"""
from fastapi import APIRouter, Body, Depends
from PromptBuilder.schemas import BuildRequest, BuildResponse
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
    return BuildResponse(ggid=req.ggid, items=items, schema_=schema)
