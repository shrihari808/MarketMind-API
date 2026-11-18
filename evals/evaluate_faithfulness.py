"""
LLM-as-a-Judge Citation Faithfulness Evaluator (Gemini Flash).
Runs WebRAGService E2E over stratified in-domain queries, extracts factual claims from
each synthesized answer, and scores the fraction of claims directly supported by the
retrieved top-5 passage chunks.

Requires GEMINI_API_KEY in environment or .env.
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List

from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.domain.interfaces.llm import LLMClient
from app.domain.schemas.rag import RAGQueryRequest
from app.infrastructure.llm.gemini import GeminiLLMClient
from app.services.web_rag import WebRAGService


class ClaimVerdict(BaseModel):
    claim: str
    supported: bool
    supporting_source_ids: List[int] = Field(default_factory=list)
    rationale: str = ""


class FaithfulnessJudgment(BaseModel):
    total_claims: int
    supported_claims: int
    verdicts: List[ClaimVerdict] = Field(default_factory=list)


async def judge_answer_faithfulness(
    llm: LLMClient,
    query: str,
    answer: str,
    passages: List[Dict[str, Any]],
) -> FaithfulnessJudgment:
    context_text = "\n\n".join(
        f"[Source {p['source']['id']}] ({p['source']['url']}):\n{p['text']}"
        for p in passages
    )
    prompt = f"""Evaluate Citation Faithfulness for the following Financial Web RAG answer.

Question: {query}

Retrieved Top-K Context Passages:
{context_text}

Synthesized Answer:
{answer}

Instructions:
1. Decompose the synthesized answer into atomic factual claims (numbers, dates, metrics, company assertions).
2. For each claim, determine `supported=true` ONLY if it is directly supported by the retrieved context passages above (ignore formatting/disclaimers).
3. Return total_claims, supported_claims, and per-claim verdicts.
"""
    return await llm.generate_structured(
        prompt=prompt,
        response_schema=FaithfulnessJudgment,
        system_prompt="You are a strict financial RAG factuality auditor. Never assume unsupported claims are true.",
    )


async def run_faithfulness_eval(
    queries_path: str = "evals/stratified_queries.json",
    output_path: str = "evals/results/faithfulness_results.json",
    limit: int = 50,
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        payload = {
            "status": "skipped",
            "reason": "GEMINI_API_KEY is not configured; cannot execute live Gemini Flash synthesis or LLM-as-a-Judge.",
        }
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return payload

    with open(queries_path, "r", encoding="utf-8") as f:
        all_queries = json.load(f)
    in_domain = [q for q in all_queries if q.get("expected_is_financial")][:limit]

    llm = GeminiLLMClient()
    rag = WebRAGService(llm_client=llm)

    records: List[Dict[str, Any]] = []
    total_claims = 0
    total_supported = 0

    for q in in_domain:
        req = RAGQueryRequest(query=q["query"], country=q.get("country", "IN"))
        res = await rag.execute(req, debug=True, retrieval_only=False)
        passages = [p.model_dump() for p in (res.selected_passages or [])]
        if not res.answer or not passages:
            records.append({
                "id": q["id"],
                "category": q.get("category"),
                "query": q["query"],
                "skipped": True,
                "reason": "Empty answer or no passages",
            })
            continue

        judgment = await judge_answer_faithfulness(llm, q["query"], res.answer, passages)
        total_claims += judgment.total_claims
        total_supported += judgment.supported_claims
        score = (judgment.supported_claims / judgment.total_claims) if judgment.total_claims else 0.0
        records.append({
            "id": q["id"],
            "category": q.get("category"),
            "query": q["query"],
            "faithfulness": round(score, 4),
            "total_claims": judgment.total_claims,
            "supported_claims": judgment.supported_claims,
            "verdicts": [v.model_dump() for v in judgment.verdicts],
        })

    macro_scores = [r["faithfulness"] for r in records if "faithfulness" in r]
    summary = {
        "status": "completed",
        "evaluated_queries": len(macro_scores),
        "total_claims": total_claims,
        "supported_claims": total_supported,
        "micro_citation_faithfulness": round(total_supported / total_claims, 4) if total_claims else 0.0,
        "macro_citation_faithfulness": round(sum(macro_scores) / len(macro_scores), 4) if macro_scores else 0.0,
    }
    payload = {"summary": summary, "records": records}
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Gemini Flash Citation Faithfulness LLM-as-a-Judge.")
    parser.add_argument("--queries", default="evals/stratified_queries.json")
    parser.add_argument("--output", default="evals/results/faithfulness_results.json")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run_faithfulness_eval(args.queries, args.output, args.limit)), indent=2))


if __name__ == "__main__":
    main()
