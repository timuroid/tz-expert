"""Main orchestration pipeline for TzeExpert."""
from __future__ import annotations

import json
import logging
from uuid import uuid4
from typing import Optional

from TzeExpert.core.settings import settings
from TzeExpert.schemas import JobRequest, JobResponse
from TzeExpert.services.clients import (
    LLMRequesterClient,
    PromptBuilderClient,
    run_step1_llm,
    run_step2_llm,
)

logger = logging.getLogger(__name__)


class TzeExpertService:
    def __init__(
        self,
        *,
        prompt_builder: Optional[PromptBuilderClient] = None,
        llm_client: Optional[LLMRequesterClient] = None,
    ) -> None:
        self._prompt_builder = prompt_builder or PromptBuilderClient()
        self._llm_client = llm_client or LLMRequesterClient()

    async def run(self, job: JobRequest) -> JobResponse:
        run_id = uuid4().hex
        logger.info(
            "job %s: pipeline started (ggid=%s)",
            run_id,
            job.ggid,
        )
        try:
            # Шаг 1
            logger.info("job %s: step1 - requesting prompts from PromptBuilder", run_id)
            step1_prompts = await self._prompt_builder.build_step1(job)
            logger.info(
                "job %s: step1 - received %d prompt groups",
                run_id,
                len(step1_prompts.items),
            )

            step1_runs = await run_step1_llm(
                llm_client=self._llm_client,
                items=step1_prompts.items,
                model=settings.LLM_MODEL,
                schema=step1_prompts.schema_,
            )
            logger.info(
                "job %s: step1 - completed LLM runs (%d parsed)",
                run_id,
                len(step1_runs),
            )
            step1_dump = [run.parsed.model_dump(mode="json") for run in step1_runs]
            step1_json = json.dumps(step1_dump, ensure_ascii=False, indent=2)
            logger.debug("job %s: step1 JSON length = %d chars", run_id, len(step1_json))

            # Шаг 2
            logger.info("job %s: step2 - requesting prompt from PromptBuilder", run_id)
            step2_prompt = await self._prompt_builder.build_step2(
                markdown=job.markdown,
                step1_results_json=step1_json,
            )
            logger.info(
                "job %s: step2 - invoking LLM for final report", run_id
            )
            final_report = await run_step2_llm(
                llm_client=self._llm_client,
                messages=step2_prompt.prompt.messages,
                model=settings.LLM_MODEL,
                schema=step2_prompt.schema_,
            )
            logger.info("job %s: step2 - LLM response received", run_id)

            logger.info(
                "job %s: pipeline finished successfully (step1_groups=%d)",
                run_id,
                len(step1_prompts.items),
            )
            return JobResponse(step1=step1_runs, step2=final_report)
        except Exception:
            logger.exception("job %s: pipeline failed", run_id)
            raise
