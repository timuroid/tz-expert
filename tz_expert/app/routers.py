# tz_expert/app/routers.py
from fastapi import APIRouter, Depends, Body, HTTPException
from tz_expert.schemas import StructuredAnalyzeRequest, StructuredAnalyzeResponse
from tz_expert.services.repository import RuleRepository
from tz_expert.services.analyzer import AnalyzerService

router = APIRouter(tags=["Structured Analysis"])


def get_repo() -> RuleRepository:
    """
    FastAPI-dependency: свежий RuleRepository на каждый запрос.
    """
    return RuleRepository()


@router.post(
    "/analyze",
    response_model=StructuredAnalyzeResponse,
    summary="Structure-Guided Group Analysis (JSON only)",
    response_description="Структурированный анализ Markdown-документа (JSON-интерфейс)"
)
async def analyze_structured(
    req: StructuredAnalyzeRequest = Body(
        ...,
        description="Запрос с полями:\n"
                    "- markdown: строка с документом в формате Markdown\n"
                    "- groups: необязательный список групп (None → все)\n"
                    "- model: необязательное имя LLM-модели"
    ),
    repo: RuleRepository = Depends(get_repo),
):
    svc = AnalyzerService(repo)
    try:
        return await svc.analyze_structured(req)
    except ValueError as e:
        # Ошибка валидации групп или другой ValueError внутри Analyzer
        raise HTTPException(status_code=400, detail=str(e))
