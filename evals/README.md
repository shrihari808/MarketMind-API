# MarketMind Web RAG Evals

This directory contains reproducible evaluation scripts, datasets, and Postman collections for measuring **Web RAG latency (p50/p95/p99)**, **retrieval Recall@k / NDCG@k / MRR across $N$ documents**, **guardrail accuracy**, and **Citation Faithfulness**.

## 1. Stratified & Baseline Evaluation Datasets
* **Stratified 55-Query Suite:** `evals/stratified_queries.json` (15 Ticker Fundamentals, 15 Breaking Market News, 15 Multi-Hop/Comparative, 10 Out-of-Domain/Adversarial)
* **Expanded Real Scraped Corpus & Tight Gold Qrels:** `evals/corpus_v2.jsonl` (`157` docs) and `evals/stratified_qrels.json` (`1–3` gold docs/query, avg `2.98`)
* **Baseline Corpus & Qrels:** `evals/corpus.jsonl` (`98` docs) and `evals/queries_with_qrels.json` (`16` queries)

## 2. Commands
```bash
# Stratified tight-gold Recall@k, NDCG@k, Hit@k, MRR across N=40, 80, 120, 157
python evals/evaluate_recall.py --corpus evals/corpus_v2.jsonl --qrels evals/stratified_qrels.json --output evals/results/recall_results_v2_stratified.json --n-steps 40 80 120 157 --ks 1 3 5 10

# Guardrail classification accuracy across all 55 stratified queries
python evals/evaluate_guardrail.py

# Gemini Flash Citation Faithfulness LLM-as-a-Judge (requires GEMINI_API_KEY)
python evals/evaluate_faithfulness.py --limit 50

# Live stage-by-stage latency benchmark (start uvicorn main:app first)
python evals/benchmark_latency.py --base-url http://127.0.0.1:8000 --queries evals/postman_queries.json
```

All measured results are documented in [`../EVALS AND METRICS.md`](../EVALS%20AND%20METRICS.md).
