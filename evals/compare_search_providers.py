"""
Head-to-Head Search Provider Comparison (DuckDuckGo vs. Brave Search).
Runs WebRAGService across the same stratified sample queries for each configured
provider (clearing TTL caches between runs) and compares latency, scrape yield,
and optionally Gemini Citation Faithfulness when GEMINI_API_KEY is set.
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.cache import clear_all_ttl_caches
from app.core.config import get_settings
from app.domain.schemas.rag import RAGQueryRequest
from app.infrastructure.llm.gemini import GeminiLLMClient
from app.infrastructure.search.factory import SearchEngineFactory
from app.services.web_rag import WebRAGService
from evals.benchmark_latency import summarize
from evals.evaluate_faithfulness import judge_answer_faithfulness


async def evaluate_provider(
    provider: str,
    queries: List[Dict[str, Any]],
    e2e: bool = False,
) -> Dict[str, Any]:
    settings = get_settings()
    await clear_all_ttl_caches()

    search_engine = SearchEngineFactory.get_search_engine(provider=provider)
    llm = GeminiLLMClient()
    rag = WebRAGService(llm_client=llm, search_engine=search_engine, vector_store=None)

    run_e2e = e2e and bool(settings.GEMINI_API_KEY)
    if not run_e2e:
        # Use deterministic heuristic analyzer during retrieval-only provider comparison
        # so both search providers receive identical sub-queries without LLM 503 variance.
        async def _fast_analyze(query: str, country: str = "IN", chat_history=None):
            res = await rag.query_analyzer._heuristic_fallback(query, country, chat_history)
            return res

        rag.query_analyzer.analyze = _fast_analyze  # type: ignore[method-assign]
    records: List[Dict[str, Any]] = []

    for q in queries:
        req = RAGQueryRequest(query=q["query"], country=q.get("country", "IN"))
        res = await rag.execute(req, debug=True, retrieval_only=not run_e2e)
        timings = res.stage_timings.model_dump() if res.stage_timings else {}

        rec: Dict[str, Any] = {
            "id": q.get("id"),
            "category": q.get("category"),
            "query": q["query"],
            "sources_count": len(res.sources),
            "answer_chars": len(res.answer),
            "stage_timings": timings,
        }

        if run_e2e and res.answer and res.selected_passages:
            try:
                judgment = await judge_answer_faithfulness(
                    llm=llm,
                    query=q["query"],
                    answer=res.answer,
                    passages=[p.model_dump() for p in res.selected_passages],
                )
                rec["faithfulness"] = (
                    round(judgment.supported_claims / judgment.total_claims, 4)
                    if judgment.total_claims
                    else 0.0
                )
                rec["total_claims"] = judgment.total_claims
                rec["supported_claims"] = judgment.supported_claims
            except Exception as exc:
                rec["faithfulness_error"] = str(exc)

        records.append(rec)

    search_ms = [r["stage_timings"].get("search_ms", 0.0) for r in records]
    scrape_ms = [r["stage_timings"].get("scrape_ms", 0.0) for r in records]
    retrieval_ms = [r["stage_timings"].get("retrieval_total_ms", 0.0) for r in records]
    total_ms = [r["stage_timings"].get("total_ms", 0.0) for r in records]

    candidates = [r["stage_timings"].get("candidates_found", 0) for r in records]
    scraped_urls = [r["stage_timings"].get("urls_scraped", 0) for r in records]
    scraped_ok = [r["stage_timings"].get("scrape_success_count", 0) for r in records]
    selected = [r["stage_timings"].get("passages_selected", 0) for r in records]
    non_empty = sum(1 for r in records if r["sources_count"] > 0)

    summary: Dict[str, Any] = {
        "provider": provider,
        "queries_evaluated": len(records),
        "e2e_with_gemini": run_e2e,
        "non_empty_source_rate": round(non_empty / len(records), 4) if records else 0.0,
        "avg_candidates_found": round(sum(candidates) / len(records), 2) if records else 0.0,
        "avg_urls_scraped": round(sum(scraped_urls) / len(records), 2) if records else 0.0,
        "avg_scrape_success_count": round(sum(scraped_ok) / len(records), 2) if records else 0.0,
        "scrape_success_rate": round(sum(scraped_ok) / sum(scraped_urls), 4) if sum(scraped_urls) else 0.0,
        "avg_passages_selected": round(sum(selected) / len(records), 2) if records else 0.0,
        "search_ms": summarize(search_ms),
        "scrape_ms": summarize(scrape_ms),
        "retrieval_total_ms": summarize(retrieval_ms),
        "total_ms": summarize(total_ms),
    }

    faith_vals = [r["faithfulness"] for r in records if "faithfulness" in r]
    if faith_vals:
        summary["avg_citation_faithfulness"] = round(sum(faith_vals) / len(faith_vals), 4)

    return {"summary": summary, "records": records}


async def compare(
    queries_path: str = "evals/stratified_queries.json",
    output_path: str = "evals/results/search_provider_comparison.json",
    limit_per_category: int = 5,
    e2e: bool = True,
) -> Dict[str, Any]:
    settings = get_settings()
    with open(queries_path, "r", encoding="utf-8") as f:
        all_queries = json.load(f)

    # Pick stratified in-domain slice
    sample: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    for q in all_queries:
        if not q.get("expected_is_financial"):
            continue
        cat = q.get("category", "general")
        if counts.get(cat, 0) < limit_per_category:
            sample.append(q)
            counts[cat] = counts.get(cat, 0) + 1

    providers = ["duckduckgo"]
    if settings.BRAVE_API_KEY and "your_brave" not in settings.BRAVE_API_KEY:
        providers.append("brave")

    results: Dict[str, Any] = {}
    for p in providers:
        results[p] = await evaluate_provider(p, sample, e2e=e2e)

    payload = {
        "queries_evaluated": len(sample),
        "providers_tested": providers,
        "summaries": {p: results[p]["summary"] for p in providers},
        "details": results,
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare DuckDuckGo vs. Brave Search in WebRAGService.")
    parser.add_argument("--queries", default="evals/stratified_queries.json")
    parser.add_argument("--output", default="evals/results/search_provider_comparison.json")
    parser.add_argument("--per-category", type=int, default=5)
    parser.add_argument("--retrieval-only", action="store_true")
    args = parser.parse_args()

    payload = asyncio.run(
        compare(
            queries_path=args.queries,
            output_path=args.output,
            limit_per_category=args.per_category,
            e2e=not args.retrieval_only,
        )
    )
    print(json.dumps(payload["summaries"], indent=2))


if __name__ == "__main__":
    main()
