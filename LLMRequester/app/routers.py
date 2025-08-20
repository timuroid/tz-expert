"""
app/routers.py
HTTP-роуты LLM Requester: один эндпойнт /v1/structured/run
"""
from fastapi import APIRouter, Body, HTTPException
from LLMRequester.schemas import RunRequest, RunResponse, Usage, Cost
from LLMRequester.services.llm_client import ask_llm, LLMError
from LLMRequester.services.pricing import normalize_model_label, price_per_1k_rub, price_per_1m_rub
from LLMRequester.services.llm_schema import default_structured_output_schema  # <-- pydantic->JSON Schema

router = APIRouter(prefix="/v1/structured", tags=["LLM Requester"])

@router.post("/run", response_model=RunResponse, summary="Выполнить один LLM-запрос (messages [+schema])")
async def run(req: RunRequest = Body(...)):
    if not req.messages or len(req.messages) < 2:
        raise HTTPException(400, detail="Provide at least 2 messages (system + user).")

    mode = req.mode or "sync"

    # Если клиент прислал schema (через алиас schema_) — используем её,
    # иначе генерируем из pydantic-модели внутри этого сервиса.
    schema_payload = req.schema_ if isinstance(req.schema_, dict) else default_structured_output_schema()

    try:
        result, usage, model_uri, attempts = await ask_llm(
            messages=[m.model_dump() for m in req.messages],
            json_schema=schema_payload,   # всегда Structured Output
            model=req.model,
        )
    except LLMError as e:
        raise HTTPException(422, detail=str(e))

    label = normalize_model_label(model_uri)
    price_1k = price_per_1k_rub(label, mode)
    price_1m = price_per_1m_rub(label, mode)
    total_tokens = int(usage.get("total_tokens", 0))
    total_rub = round((total_tokens / 1000.0) * price_1k, 6)

    return RunResponse(
        result=result,
        usage=Usage(
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=total_tokens,
        ),
        cost=Cost(
            model_label=label,
            mode=mode,
            price_per_1m=price_1m,
            total_rub=total_rub,
        ),
        model_uri=model_uri,
        attempts=attempts,
    )
