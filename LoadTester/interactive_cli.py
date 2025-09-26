import asyncio
import json
import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .llm_load_tester import run_load, summarize


def _ask(prompt: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val if val else (default or "")


def _to_int(s: str, default: int) -> int:
    try:
        return int(s)
    except Exception:
        return default


def _to_float(s: str, default: float) -> float:
    try:
        return float(s)
    except Exception:
        return default


def _build_messages(question: str, target_tokens: int) -> List[Dict[str, str]]:
    if not question:
        question = (
            "Сгенерируй как можно более длинный, бессмысленный текст примерно на "
            f"{target_tokens} токенов, без списков и форматирования, русскими словами."
        )
    sys = "You are a helpful and concise assistant."
    # Мы просим длинный ответ, но конечный провайдер может ограничить ответ по max tokens
    # на своей стороне — это нормально для данного замера.
    return [
        {"role": "system", "content": sys},
        {
            "role": "user",
            "content": (
                question
                + "\n\nПостарайся дать единый сплошной абзац без форматирования,"
                " избегай пунктов и подзаголовков."
            ),
        },
    ]


def main() -> None:
    print("LLMRequester Interactive Load Test")
    print("— Ответы зависят от лимитов провайдера/сервиса —")

    default_url = os.getenv("LLM_REQUESTER_RUN_URL", "http://localhost:8020/v1/structured/run")
    url = _ask("Target URL", default_url)

    concurrency = _to_int(_ask("Concurrency", "50"), 50)

    mode = _ask("Mode: fixed or duration", "fixed").lower()
    total_requests: Optional[int] = None
    duration_sec: Optional[float] = None
    if mode.startswith("dur"):
        duration_sec = _to_float(_ask("Duration (sec)", "30"), 30.0)
    else:
        # Для оценки «как долго обрабатываются 50 параллельных запросов»
        # удобно отправить ровно столько же запросов, сколько конкуренция.
        total_requests = _to_int(_ask("Total requests", str(concurrency)), concurrency)

    target_tokens = _to_int(_ask("Approx target output tokens", "2000"), 2000)
    question = _ask("Your question/prompt (empty for default)", "")
    messages = _build_messages(question, target_tokens)

    timeout = _to_float(_ask("Per-request timeout (sec)", "120"), 120.0)
    jitter_ms = _to_int(_ask("Jitter before send (ms)", "0"), 0)

    out_default = f"llm_requests/load_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    out_path = _ask("Save CSV to (empty to skip)", out_default)
    if not out_path:
        out_path = None

    # logging setup
    log_level = _ask("Log level (DEBUG/INFO/WARN/ERROR)", "INFO").upper()
    log_file_default = f"llm_requests/load_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file = _ask("Save log to (empty to skip)", log_file_default)
    if not log_file:
        log_file = None

    logger = logging.getLogger("llm_load_tester")
    level = getattr(logging, log_level, logging.INFO)
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    logger.handlers.clear()
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if log_file:
        import pathlib

        pathlib.Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    print("\nRunning...\n")

    records, elapsed = asyncio.run(
        run_load(
            url,
            total_requests=total_requests,
            duration_sec=duration_sec,
            concurrency=concurrency,
            schema=None,
            timeout=timeout,
            jitter_ms=jitter_ms,
            messages=messages,
        )
    )

    stats = summarize(records, elapsed)
    print("SUMMARY:")
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    if out_path:
        # Небольшая локальная запись CSV — используем функцию из тестера
        from .llm_load_tester import save_csv
        import pathlib

        save_csv(records, pathlib.Path(out_path))
        print(f"Saved CSV: {out_path}")


if __name__ == "__main__":
    main()
