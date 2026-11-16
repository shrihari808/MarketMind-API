"""
Live Web RAG Stage-by-Stage Latency Benchmark.
Calls POST /api/v2/rag/web?stream=false&debug=true&retrieval_only=true across a suite
of real financial queries and computes p50/p90/p95/p99 per pipeline stage.
"""

import argparse
import asyncio
import json
import math
import os
import time
from typing import Any, Dict, List

import httpx


def percentile(values: List[float], pct: float) -> float:
    """Linear-interpolated percentile (type 7, matching NumPy default)."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(sorted_vals[int(k)], 2)
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return round(d0 + d1, 2)


def summarize(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"count": 0, "min": 0.0, "mean": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    return {
        "count": len(values),
        "min": round(min(values), 2),
        "mean": round(sum(values) / len(values), 2),
        "p50": percentile(values, 50),
        "p90": percentile(values, 90),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": round(max(values), 2),
    }


async def run_benchmark(
    base_url: str,
    queries_path: str,
    output_path: str,
    repeats: int = 1,
    concurrency: int = 1,
    retrieval_only: bool = True,
) -> Dict[str, Any]:
    with open(queries_path, "r", encoding="utf-8") as f:
        queries = json.load(f)

    workload = queries * repeats
    semaphore = asyncio.Semaphore(concurrency)
    records: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
        # Disable rate limit during local benchmark if possible
        try:
            await client.post("/api/v2/health/rate-limit", json={"enabled": False, "reset_history": True})
        except Exception:
            pass

        async def _run_one(idx: int, item: Dict[str, str]) -> Dict[str, Any]:
            async with semaphore:
                t0 = time.perf_counter()
                try:
                    resp = await client.post(
                        "/api/v2/rag/web",
                        params={
                            "stream": "false",
                            "debug": "true",
                            "retrieval_only": "true" if retrieval_only else "false",
                        },
                        headers={"X-Client-ID": f"eval-bench-{idx}"},
                        json={"query": item["query"], "country": item.get("country", "IN")},
                    )
                    http_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                    if resp.status_code != 200:
                        return {
                            "idx": idx,
                            "query": item["query"],
                            "country": item.get("country", "IN"),
                            "status_code": resp.status_code,
                            "http_ms": http_ms,
                            "error": resp.text[:300],
                        }
                    body = resp.json()
                    return {
                        "idx": idx,
                        "query": item["query"],
                        "country": item.get("country", "IN"),
                        "status_code": resp.status_code,
                        "http_ms": http_ms,
                        "sources_count": len(body.get("sources", [])),
                        "answer_chars": len(body.get("answer", "")),
                        "stage_timings": body.get("stage_timings") or {},
                    }
                except Exception as exc:
                    return {
                        "idx": idx,
                        "query": item["query"],
                        "country": item.get("country", "IN"),
                        "status_code": 0,
                        "http_ms": round((time.perf_counter() - t0) * 1000.0, 2),
                        "error": str(exc),
                    }

        tasks = [_run_one(i, q) for i, q in enumerate(workload)]
        records = await asyncio.gather(*tasks)

    ok_records = [r for r in records if r.get("status_code") == 200]
    err_records = [r for r in records if r.get("status_code") != 200]

    stage_keys = [
        "query_analysis_ms",
        "cache_lookup_ms",
        "search_ms",
        "pre_filter_ms",
        "scrape_ms",
        "chunk_extract_ms",
        "rerank_ms",
        "quote_ms",
        "retrieval_total_ms",
        "llm_ttft_ms",
        "llm_total_ms",
        "total_ms",
    ]
    count_keys = [
        "candidates_found",
        "urls_scraped",
        "scrape_success_count",
        "passages_extracted",
        "passages_selected",
    ]

    summary: Dict[str, Any] = {
        "total_requests": len(records),
        "success_count": len(ok_records),
        "error_count": len(err_records),
        "concurrency": concurrency,
        "retrieval_only": retrieval_only,
        "http_ms": summarize([r["http_ms"] for r in ok_records]),
        "stages_ms": {},
        "funnel_averages": {},
    }

    for k in stage_keys:
        vals = [
            float(r["stage_timings"][k])
            for r in ok_records
            if r.get("stage_timings") and r["stage_timings"].get(k) is not None
        ]
        if vals:
            summary["stages_ms"][k] = summarize(vals)

    for k in count_keys:
        vals = [
            float(r["stage_timings"][k])
            for r in ok_records
            if r.get("stage_timings") and r["stage_timings"].get(k) is not None
        ]
        if vals:
            summary["funnel_averages"][k] = round(sum(vals) / len(vals), 2)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    payload = {"summary": summary, "records": records}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Web RAG latency.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--queries", default="evals/postman_queries.json")
    parser.add_argument("--output", default="evals/results/latency_results.json")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--e2e", action="store_true", help="Include LLM synthesis (requires GEMINI_API_KEY)")
    args = parser.parse_args()

    payload = asyncio.run(
        run_benchmark(
            base_url=args.base_url,
            queries_path=args.queries,
            output_path=args.output,
            repeats=args.repeats,
            concurrency=args.concurrency,
            retrieval_only=not args.e2e,
        )
    )
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
