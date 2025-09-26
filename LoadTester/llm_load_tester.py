import asyncio
import dataclasses
import json
import os
import random
import statistics
import time
import logging
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx


logger = logging.getLogger("llm_load_tester")


@dataclasses.dataclass
class RequestRecord:
    id: int
    status: int
    ok: bool
    error: Optional[str]
    latency_ms: float
    queued_at: str
    started_at: str
    ended_at: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_messages() -> List[Dict[str, str]]:
    user_variants = [
        "Скажи 'ок' одним словом.",
        "Сколько будет 2+2? Ответь числом.",
        "Напиши слово 'кот'.",
        "Назови первую букву русского алфавита.",
        "Ответь 'да'.",
    ]
    return [
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": random.choice(user_variants)},
    ]


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    k = (len(values) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return d0 + d1


async def _one_call(
    client: httpx.AsyncClient,
    url: str,
    idx: int,
    messages: Optional[List[Dict[str, str]]],
    schema: Optional[Dict[str, Any]],
) -> RequestRecord:
    queued_at = _now_iso()
    t0 = time.monotonic()
    started_at = _now_iso()
    try:
        payload: Dict[str, Any] = {
            "messages": messages or default_messages(),
        }
        if schema is not None:
            payload["schema"] = schema
        logger.debug(f"req#{idx} send -> {url}")
        resp = await client.post(url, json=payload)
        ended_at = _now_iso()
        latency = (time.monotonic() - t0) * 1000.0
        ok = resp.status_code == 200
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        err = None
        if ok:
            try:
                data = resp.json()
                u = data.get("usage") or {}
                usage = {
                    "prompt_tokens": int(u.get("prompt_tokens", 0)),
                    "completion_tokens": int(u.get("completion_tokens", 0)),
                    "total_tokens": int(u.get("total_tokens", 0)),
                }
                logger.debug(
                    f"req#{idx} recv <- 200 latency_ms={latency:.2f} total_tokens={usage['total_tokens']}"
                )
            except Exception as exc:  # noqa: BLE001
                ok = False
                err = f"json_parse: {exc}"
                logger.warning(f"req#{idx} json parse error: {err}")
        else:
            try:
                err = resp.text[:500]
            except Exception:  # noqa: BLE001
                err = f"HTTP {resp.status_code}"
            logger.warning(
                f"req#{idx} error status={resp.status_code} latency_ms={latency:.2f} err={err}"
            )

        return RequestRecord(
            id=idx,
            status=resp.status_code,
            ok=ok,
            error=err,
            latency_ms=latency,
            queued_at=queued_at,
            started_at=started_at,
            ended_at=ended_at,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
        )
    except Exception as exc:  # noqa: BLE001
        ended_at = _now_iso()
        latency = (time.monotonic() - t0) * 1000.0
        logger.warning(f"req#{idx} exception: {exc}")
        return RequestRecord(
            id=idx,
            status=0,
            ok=False,
            error=str(exc)[:500],
            latency_ms=latency,
            queued_at=queued_at,
            started_at=started_at,
            ended_at=ended_at,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )


async def run_load(
    url: str,
    *,
    total_requests: Optional[int],
    duration_sec: Optional[float],
    concurrency: int,
    schema: Optional[Dict[str, Any]] = None,
    timeout: float = 60.0,
    jitter_ms: int = 0,
    messages: Optional[List[Dict[str, str]]] = None,
) -> Tuple[List[RequestRecord], float]:
    assert total_requests or duration_sec, "Provide --requests or --duration"
    logger.info(
        f"Starting load: url={url} total_requests={total_requests} duration={duration_sec} concurrency={concurrency} timeout={timeout}s jitter_ms={jitter_ms}"
    )

    results: List[RequestRecord] = []
    limiter = asyncio.Semaphore(concurrency)
    started = time.monotonic()
    idx_counter = 0

    async def worker_task(idx: int) -> None:
        nonlocal results
        async with limiter:
            if jitter_ms > 0:
                await asyncio.sleep(random.random() * jitter_ms / 1000.0)
            rec = await _one_call(client, url, idx, messages, schema)
            results.append(rec)

    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        tasks: List[asyncio.Task] = []

        if total_requests is not None:
            for _ in range(total_requests):
                idx_counter += 1
                tasks.append(asyncio.create_task(worker_task(idx_counter)))
                # keep the task list from growing too large
                if len(tasks) >= concurrency * 4:
                    await asyncio.gather(*tasks)
                    tasks.clear()
            if tasks:
                await asyncio.gather(*tasks)
        else:
            assert duration_sec is not None
            while (time.monotonic() - started) < duration_sec:
                idx_counter += 1
                tasks.append(asyncio.create_task(worker_task(idx_counter)))
                if len(tasks) >= concurrency * 4:
                    await asyncio.gather(*tasks)
                    tasks.clear()
            if tasks:
                await asyncio.gather(*tasks)

    elapsed = time.monotonic() - started
    try:
        rps = (len(results) / elapsed) if elapsed > 0 else 0.0
        logger.info(
            f"Finished load: elapsed={elapsed:.3f}s total={len(results)} rps={rps:.2f} ok={sum(1 for r in results if r.ok)} fail={sum(1 for r in results if not r.ok)}"
        )
    except Exception:
        pass
    return results, elapsed


def summarize(records: List[RequestRecord], elapsed: float) -> Dict[str, Any]:
    total = len(records)
    ok = sum(1 for r in records if r.ok)
    fail = total - ok
    latencies = sorted(r.latency_ms for r in records if r.latency_ms >= 0)
    prompt_toks = sum(r.prompt_tokens for r in records)
    comp_toks = sum(r.completion_tokens for r in records)
    total_toks = sum(r.total_tokens for r in records)
    codes: Dict[int, int] = {}
    for r in records:
        codes[r.status] = codes.get(r.status, 0) + 1

    summary = {
        "total_requests": total,
        "success": ok,
        "fail": fail,
        "duration_sec": round(elapsed, 3),
        "rps": round(total / elapsed if elapsed > 0 else 0.0, 3),
        "latency_ms": {
            "min": round(latencies[0], 2) if latencies else 0.0,
            "avg": round(statistics.mean(latencies), 2) if latencies else 0.0,
            "median": round(statistics.median(latencies), 2) if latencies else 0.0,
            "p90": round(percentile(latencies, 90), 2) if latencies else 0.0,
            "p95": round(percentile(latencies, 95), 2) if latencies else 0.0,
            "p99": round(percentile(latencies, 99), 2) if latencies else 0.0,
            "max": round(latencies[-1], 2) if latencies else 0.0,
        },
        "status_codes": codes,
        "tokens": {
            "prompt": prompt_toks,
            "completion": comp_toks,
            "total": total_toks,
            "avg_total_per_req": round((total_toks / total) if total > 0 else 0, 2),
        },
    }
    return summary


def save_csv(records: List[RequestRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(
            "id,status,ok,latency_ms,queued_at,started_at,ended_at,prompt_tokens,completion_tokens,total_tokens,error\n"
        )
        for r in records:
            err = (r.error or "").replace("\n", " ").replace(",", " ")
            f.write(
                f"{r.id},{r.status},{int(r.ok)},{round(r.latency_ms,2)},{r.queued_at},{r.started_at},{r.ended_at},{r.prompt_tokens},{r.completion_tokens},{r.total_tokens},{err}\n"
            )


def main() -> None:
    parser = ArgumentParser(description="LLMRequester load tester")
    parser.add_argument(
        "--url",
        default=os.getenv("LLM_REQUESTER_RUN_URL", "http://localhost:8020/v1/structured/run"),
        help="Target endpoint URL (POST)",
    )
    parser.add_argument("--requests", type=int, default=100, help="Total number of requests (mutually exclusive with --duration)")
    parser.add_argument("--duration", type=float, default=None, help="Duration in seconds instead of fixed requests")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent requests")
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-request timeout (seconds)")
    parser.add_argument("--jitter-ms", type=int, default=0, help="Random pre-send jitter per request (ms)")
    parser.add_argument("--schema-json", type=str, default=None, help="Optional JSON schema to enforce structured output")
    parser.add_argument("--messages-json", type=str, default=None, help="Optional fixed messages JSON array")
    parser.add_argument("--out", type=str, default=None, help="Optional CSV output path for per-request metrics")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level (DEBUG/INFO/WARN/ERROR)")
    parser.add_argument("--log-file", type=str, default=None, help="Optional log file path")

    args = parser.parse_args()

    schema = None
    if args.schema_json:
        schema = json.loads(args.schema_json)

    messages = None
    if args.messages_json:
        messages = json.loads(args.messages_json)

    # setup logging
    level_name = (args.log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    # clear existing handlers to avoid duplicates
    logger.handlers.clear()
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if args.log_file:
        Path(args.log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(args.log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    results, elapsed = asyncio.run(
        run_load(
            args.url,
            total_requests=None if args.duration else args.requests,
            duration_sec=args.duration,
            concurrency=args.concurrency,
            schema=schema,
            timeout=args.timeout,
            jitter_ms=args.jitter_ms,
            messages=messages,
        )
    )

    stats = summarize(results, elapsed)
    print("SUMMARY:")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    try:
        logger.info(
            f"Latency p95={stats['latency_ms']['p95']}ms max={stats['latency_ms']['max']}ms status_codes={stats['status_codes']} tokens_avg={stats['tokens']['avg_total_per_req']}"
        )
    except Exception:
        pass

    if args.out:
        out_path = Path(args.out)
        save_csv(results, out_path)
        print(f"Saved CSV: {out_path}")


if __name__ == "__main__":
    main()
