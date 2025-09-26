"""HTTP clients for PromptBuilder and LLMRequester."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import httpx
from pydantic import ValidationError

from PromptBuilder.schemas import (
    BuildItem,
    Step1BuildRequest,
    Step1BuildResponse,
    Step2BuildRequest,
    Step2BuildResponse,
)
from LLMRequester.schemas import RunRequest, RunResponse

from TzeExpert.core.settings import build_llm_endpoint, build_prompt_builder_endpoint, settings
from TzeExpert.schemas import JobRequest, GroupResult, Step1Run, SectionPlanOutput

logger = logging.getLogger(__name__)

# Directory to persist all LLMRequester requests/responses
_LLM_CALLS_DIR = Path(__file__).resolve().parents[2] / "var" / "llm_calls"
_LLM_CALLS_DIR.mkdir(parents=True, exist_ok=True)


class PromptBuilderClient:
    def __init__(self, *, timeout: float = 60.0) -> None:
        self._timeout = timeout

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = build_prompt_builder_endpoint(path)
        logger.info("PromptBuilderClient: POST %s", url)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:  # type: ignore[attr-defined]
            logger.error(
                "PromptBuilderClient: POST %s failed (status=%s, body=%s)",
                url,
                exc.response.status_code if exc.response else "?",
                (exc.response.text if exc.response else "<no body>")[:500],
            )
            raise
        logger.info(
            "PromptBuilderClient: POST %s succeeded (status=%s)",
            url,
            resp.status_code,
        )
        return resp.json()

    async def build_step1(self, job: JobRequest) -> Step1BuildResponse:
        limit = settings.STEP1_LIMIT
        logger.info(
            "PromptBuilderClient: build_step1 (ggid=%s, limit=%s)",
            job.ggid,
            limit,
        )
        payload = Step1BuildRequest(
            markdown=job.markdown,
            ggid=job.ggid,
            limit=limit,
        ).model_dump()
        data = await self._post("/step1/build", payload)
        response = Step1BuildResponse(**data)
        logger.info(
            "PromptBuilderClient: build_step1 completed (groups=%d)",
            len(response.items),
        )
        return response

    async def build_step2(
        self,
        *,
        markdown: str,
        step1_results_json: str,
    ) -> Step2BuildResponse:
        logger.info(
            "PromptBuilderClient: build_step2 (step1_json_len=%d)",
            len(step1_results_json),
        )
        payload = Step2BuildRequest(
            markdown=markdown,
            step1_results=step1_results_json,
        ).model_dump()
        data = await self._post("/step2/build", payload)
        response = Step2BuildResponse(**data)
        logger.info(
            "PromptBuilderClient: build_step2 completed (messages=%d)",
            len(response.prompt.messages),
        )
        return response


class LLMRequesterClient:
    def __init__(self, *, timeout: Optional[float] = None) -> None:
        """
        LLM requester HTTP client.

        timeout:
            - None => disable client-side timeouts (wait indefinitely until LLMRequester responds).
            - float (seconds) => apply that overall timeout to the HTTP call.
        """
        self._timeout = httpx.Timeout(None) if timeout is None else httpx.Timeout(timeout)

    async def run(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        extra_logs: Optional[Dict[str, Any]] = None,
    ) -> RunResponse:
        payload = RunRequest(messages=messages, model=model, schema=schema).model_dump(by_alias=True)
        url = build_llm_endpoint("/run")
        logger.info(
            "LLMRequesterClient: POST %s (messages=%d, schema=%s)",
            url,
            len(messages),
            "yes" if schema else "no",
        )

        ts = datetime.now()
        day_dir = _LLM_CALLS_DIR / ts.strftime("%Y%m%d")
        day_dir.mkdir(exist_ok=True)
        stamp = ts.strftime("%H%M%S_%f")
        req_path = day_dir / f"{stamp}_request.json"
        try:
            req_path.write_text(
                json.dumps({"url": url, "payload": payload}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.debug("LLMRequesterClient: failed to persist request to %s", req_path)

        # Optionally persist additional artifacts alongside the request/response
        if extra_logs:
            for key, value in extra_logs.items():
                try:
                    extra_path = day_dir / f"{stamp}_{key}.json"
                    if isinstance(value, str):
                        extra_path.write_text(value, encoding="utf-8")
                    else:
                        extra_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    logger.debug("LLMRequesterClient: failed to persist extra log '%s'", key)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:  # type: ignore[attr-defined]
            body_preview = (exc.response.text if exc.response else "<no body>")[:500]
            logger.error(
                "LLMRequesterClient: POST %s failed (status=%s, body=%s)",
                url,
                exc.response.status_code if exc.response else "?",
                body_preview,
            )
            raise

        logger.info(
            "LLMRequesterClient: POST %s succeeded (status=%s)",
            url,
            resp.status_code,
        )

        data = resp.json()

        resp_path = day_dir / f"{stamp}_response.json"
        try:
            resp_path.write_text(
                json.dumps(
                    {
                        "status": resp.status_code,
                        "url": str(resp.request.url) if getattr(resp, "request", None) else url,
                        "result": data,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            logger.debug("LLMRequesterClient: failed to persist response to %s", resp_path)

        return RunResponse(**data)


def _parse_step1_run(raw_text: str, item: BuildItem) -> Step1Run:
    try:
        parsed = GroupResult.model_validate_json(raw_text)
    except ValidationError as exc:
        raise ValueError(f"Failed to parse Step1 JSON for group {item.groupId}: {exc}") from exc
    if parsed.group_id != item.groupId:
        parsed = parsed.model_copy(update={"group_id": item.groupId})
    return Step1Run(group_id=item.groupId, raw=raw_text, parsed=parsed)


def _parse_step2(raw_text: str) -> SectionPlanOutput:
    try:
        return SectionPlanOutput.model_validate_json(raw_text)
    except ValidationError as exc:
        raise ValueError(f"Failed to parse Step2 JSON: {exc}") from exc


async def run_step1_llm(
    *,
    llm_client: LLMRequesterClient,
    items: Sequence[BuildItem],
    model: Optional[str],
    schema: Dict[str, Any],
) -> List[Step1Run]:
    # Log outbound requests per group
    for item in items:
        logger.info(
            "step1: sending LLM request for group id=%s code=%s name=%s",
            item.groupId,
            item.groupCode,
            item.groupName,
        )
    responses = await asyncio.gather(
        *[
            llm_client.run(item.messages, model=model, schema=schema)
            for item in items
        ]
    )
    runs: List[Step1Run] = []
    for item, response in zip(items, responses):
        # Log inbound responses per group
        try:
            pt = int(getattr(response.usage, "prompt_tokens", 0))
            ct = int(getattr(response.usage, "completion_tokens", 0))
            tt = int(getattr(response.usage, "total_tokens", 0))
        except Exception:
            pt = ct = tt = 0
        logger.info(
            "step1: received LLM response for group id=%s code=%s (attempts=%s, tokens=%s/%s/%s)",
            item.groupId,
            item.groupCode,
            getattr(response, "attempts", "?"),
            pt,
            ct,
            tt,
        )
        raw = response.result if isinstance(response.result, str) else json.dumps(response.result, ensure_ascii=False)
        runs.append(_parse_step1_run(raw, item))
    return runs


async def run_step2_llm(
    *,
    llm_client: LLMRequesterClient,
    messages: List[Dict[str, str]],
    model: Optional[str],
    schema: Dict[str, Any],
    instances_json_log: Optional[str] = None,
) -> SectionPlanOutput:
    extra = {"step2_instances": instances_json_log} if instances_json_log is not None else None
    resp = await llm_client.run(messages, model=model, schema=schema, extra_logs=extra)
    raw = resp.result if isinstance(resp.result, str) else json.dumps(resp.result, ensure_ascii=False)
    return _parse_step2(raw)
