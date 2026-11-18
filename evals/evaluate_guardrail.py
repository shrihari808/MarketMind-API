"""
Evaluates QueryAnalyzer financial guardrail classification across the 55 stratified queries
(45 in-domain financial across 3 categories + 10 out-of-domain / adversarial queries).
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.market.yfinance_client import YFinanceMarketClient
from app.services.query_analyzer import QueryAnalyzer


async def evaluate_guardrail(
    queries_path: str = "evals/stratified_queries.json",
    output_path: str = "evals/results/guardrail_results.json",
) -> Dict[str, Any]:
    with open(queries_path, "r", encoding="utf-8") as f:
        queries = json.load(f)

    analyzer = QueryAnalyzer(market_client=YFinanceMarketClient())
    records: List[Dict[str, Any]] = []

    tp = fp = tn = fn = 0
    by_category: Dict[str, Dict[str, int]] = {}

    for q in queries:
        expected = bool(q["expected_is_financial"])
        res = await analyzer.analyze(query=q["query"], country=q.get("country", "IN"))
        predicted = bool(res.is_financial)
        correct = predicted == expected

        if expected and predicted:
            tp += 1
        elif not expected and predicted:
            fp += 1
        elif not expected and not predicted:
            tn += 1
        else:
            fn += 1

        cat = q["category"]
        by_category.setdefault(cat, {"total": 0, "correct": 0})
        by_category[cat]["total"] += 1
        if correct:
            by_category[cat]["correct"] += 1

        records.append({
            "id": q["id"],
            "category": cat,
            "query": q["query"],
            "expected_is_financial": expected,
            "predicted_is_financial": predicted,
            "correct": correct,
            "detected_ticker": res.detected_ticker,
            "reason": res.financial_reason,
        })

    total = len(queries)
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    abstention_rate = tn / (tn + fp) if (tn + fp) else 0.0
    false_positive_rate = fp / (tn + fp) if (tn + fp) else 0.0

    summary = {
        "total_queries": total,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "ood_abstention_rate": round(abstention_rate, 4),
        "ood_false_positive_rate": round(false_positive_rate, 4),
        "by_category": {
            cat: {
                **counts,
                "accuracy": round(counts["correct"] / counts["total"], 4) if counts["total"] else 0.0,
            }
            for cat, counts in by_category.items()
        },
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    payload = {"summary": summary, "records": records}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def main() -> None:
    payload = asyncio.run(evaluate_guardrail())
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
