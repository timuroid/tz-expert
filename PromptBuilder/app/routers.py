"""HTTP‑роуты PromptBuilder (оставлены только Step1/Step2).

Использование:
- POST /v1/prompt-builder/step1/build — сборка промптов по группам
- POST /v1/prompt-builder/step2/build — сборка финального промпта для плана по разделам
"""
from fastapi import APIRouter, Body, Depends
import logging

from PromptBuilder.schemas import (
    Step1BuildRequest,
    Step1BuildResponse,
    Step2BuildRequest,
    Step2BuildResponse,
)
from PromptBuilder.services.builder import PromptBuilderService
from PromptBuilder.services.repository import Repo


router = APIRouter(prefix="/v1/prompt-builder", tags=["PromptBuilder"])
_log = logging.getLogger(__name__)


def get_repo() -> Repo:
    """Небольшой DI‑хелпер: вернуть новый экземпляр репозитория."""
    return Repo()


@router.post("/step1/build", response_model=Step1BuildResponse, summary="Step 1: build prompts by groups")
def build_step1(req: Step1BuildRequest = Body(...), repo: Repo = Depends(get_repo)):
    """Собрать промпты и схему для шага 1 по указанному GG."""
    _log.info("HTTP step1/build called (ggid=%s, limit=%s)", req.ggid, getattr(req, "limit", None))
    svc = PromptBuilderService(repo)
    return svc.build_step1_response(req)


@router.post("/step2/build", response_model=Step2BuildResponse, summary="Step 2: build prompt for final plan")
def build_step2(req: Step2BuildRequest = Body(...)):
    """Собрать промпт и схему для шага 2 на основании результатов шага 1."""
    _log.info("HTTP step2/build called (markdown_len=%s, step1_json_len=%s)", len(req.markdown), len(req.step1_results))
    svc = PromptBuilderService()
    return svc.build_step2_prompt(req)
