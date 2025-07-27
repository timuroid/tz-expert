from fastapi import APIRouter, Body, Depends
from tz_expert.schemas import AnalyzeRequest, AnalyzeResponse
from tz_expert.services.analyzer import AnalyzerService

router = APIRouter(tags=["Analysis"])

@router.get("/errors", tags=["Rules"])
async def list_rules(svc: AnalyzerService = Depends()):
    """Вернуть YAML-справочник правил (как и раньше)."""
    return svc.list_rules()

@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="LLM-анализ ТЗ",
    response_description="Найдённые ошибки и статистика токенов",
    tags=["Analysis"],
)
async def analyze(
    req: AnalyzeRequest = Body(
        ...,
        examples={
            "simple": {
                "summary": "Мини-документ, 1 ошибка",
                "value": {
                    "html": "<h1>ТЗ</h1><p>…</p>",
                    "codes": ["E02"],
                    "model": "yandexgpt/latest"
                },
            }
        },
    ),
    svc: AnalyzerService = Depends(),
):
    """
    1. **triage-group** — быстрый batched-поиск ошибок.<br>
    2. **triage-single** — доп. точечные проверки.<br>
    3. **deep** — детальный отчёт по найденным ошибкам.

    Используйте `codes` **или** `groups`. Если оба списка пусты — берутся
    все группы по умолчанию.
    """
    return await svc.analyze(req)
