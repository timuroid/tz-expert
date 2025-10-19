"""
HTTP‑роуты FastAPI для сервиса LLMRequester.

Основной эндпоинт: `/v1/structured/run`. Принимает сообщения (messages),
опциональную JSON‑схему и модель и возвращает результат вызова провайдера
(текст или JSON), а также usage и стоимость.
"""
import logging
from fastapi import APIRouter, Body, HTTPException

from LLMRequester.schemas import RunRequest, RunResponse, Usage, Cost
from LLMRequester.services.llm_client import ask_llm, LLMError
from LLMRequester.services.pricing import normalize_model_label, price_per_1k_rub, price_per_1m_rub

router = APIRouter(prefix="/v1/structured", tags=["LLM Requester"])
logger = logging.getLogger(__name__)


@router.post("/run", response_model=RunResponse, summary="Вызов LLM (messages [+schema])")
async def run(req: RunRequest = Body(...)):
    """
    Основной RPC‑эндпоинт LLMRequester.

    Валидация входа:
    - Требуется минимум 2 сообщения (как правило, system + user).
    - `schema` (если передана) проксируется в провайдера через response_format.

    Поток выполнения:
    1) Логируем запрос (число сообщений, наличие схемы, модель).
    2) Вызываем клиент `ask_llm`, получаем результат/usage/URI/попытки.
    3) Рассчитываем стоимость по модели, строим ответ.

    Ошибки:
    - Любая LLMError маппится на соответствующий HTTP‑статус и detail с полями
      code/message/attempts/model_uri/(provider_status).
    - Прочие исключения -> 500 Internal Server Error.
    """
    if not req.messages or len(req.messages) < 2:
        raise HTTPException(400, detail="Provide at least 2 messages (system + user).")

    # mode has been removed from API; pricing is per-model only
    schema_payload = req.schema_ if isinstance(req.schema_, dict) else None

    try:
        logger.info(
            "run: request messages=%s schema=%s model=%s",
            len(req.messages),
            "yes" if schema_payload else "no",
            req.model or "<default>",
        )
        result, usage, model_uri, attempts = await ask_llm(
            messages=[m.model_dump() for m in req.messages],
            json_schema=schema_payload,
            model=req.model,
        )
    except LLMError as exc:
        logger.warning(
            "run: LLMError code=%s status=%s attempts=%s provider_status=%s msg=%s",
            getattr(exc, "code", None),
            getattr(exc, "status_code", None),
            getattr(exc, "attempts", None),
            getattr(exc, "provider_status", None),
            str(exc),
        )
        detail = {
            "code": getattr(exc, "code", "provider_error"),
            "message": str(exc),
            "attempts": getattr(exc, "attempts", None),
            "model_uri": getattr(exc, "model_uri", None),
        }
        prov_status = getattr(exc, "provider_status", None)
        if prov_status is not None:
            detail["provider_status"] = prov_status
        raise HTTPException(getattr(exc, "status_code", 422), detail=detail)
    except Exception:
        logger.exception("run: unexpected error")
        raise HTTPException(500, detail="Internal Server Error")

    label = normalize_model_label(model_uri)
    price_1k = price_per_1k_rub(label)
    price_1m = price_per_1m_rub(label)
    total_tokens = int(usage.get("total_tokens", 0))
    total_rub = round((total_tokens / 1000.0) * price_1k, 6)

    logger.info(
        "run: success model=%s attempts=%s tokens=%s cost_rub=%s",
        label,
        attempts,
        total_tokens,
        total_rub,
    )

    return RunResponse(
        result=result,
        usage=Usage(
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=total_tokens,
        ),
        cost=Cost(
            model_label=label,
            price_per_1m=price_1m,
            total_rub=total_rub,
        ),
        model_uri=model_uri,
        attempts=attempts,
    )
