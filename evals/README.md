# MarketMind Web RAG Evals (`evals` branch)

This directory contains reproducible evaluation scripts, datasets, and Postman collections for measuring **Web RAG latency (p50/p95/p99)** and **retrieval Recall@k across $N$ documents**.

## 1. Debug Instrumentation Added
* [`app/domain/schemas/rag.py`](../app/domain/schemas/rag.py): Added `RAGStageTimings` and optional `stage_timings` / `selected_passages` fields on `RAGResult`.
* [`app/services/web_rag.py`](../app/services/web_rag.py): Added per-stage `time.perf_counter()` instrumentation (`query_analysis_ms`, `cache_lookup_ms`, `search_ms`, `pre_filter_ms`, `scrape_ms`, `chunk_extract_ms`, `rerank_ms`, `quote_ms`, `retrieval_total_ms`, `llm_ttft_ms`, `llm_total_ms`, `total_ms`) plus `debug` and `retrieval_only` flags on `stream()` / `execute()`.
* [`app/api/v2/endpoints/rag.py`](../app/api/v2/endpoints/rag.py): Exposed `?debug=true` and `?retrieval_only=true` query parameters on `POST /api/v2/rag/web` and response headers `X-RAG-Retrieval-Ms` / `X-RAG-Total-Ms`.

## 2. Recall@k Across $N$ Documents
* **Corpus**: `evals/corpus.jsonl` (98 scraped financial web articles across 16 queries).
* **Qrels**: `evals/queries_with_qrels.json` (entity + multi-term topical relevance ground truth).
* Re-run evaluation:
  ```bash
  python evals/evaluate_recall.py --n-steps 25 50 75 98 --ks 1 3 5 10
  ```
* Rebuild corpus from live DuckDuckGo + Trafilatura:
  ```bash
  python evals/build_corpus.py
  ```

## 3. Latency Benchmarking (Python + Postman CLI)
Start the API locally:
```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

### Stage-by-stage Python benchmark
```bash
# Retrieval-only (no GEMINI_API_KEY required)
python evals/benchmark_latency.py --base-url http://127.0.0.1:8000 --queries evals/postman_queries.json

# Full End-to-End including Gemini synthesis (requires GEMINI_API_KEY in .env)
python evals/benchmark_latency.py --base-url http://127.0.0.1:8000 --queries evals/postman_queries.json --e2e
```

### Postman CLI functional & performance runs
Disable the 25 req/min IP rate limiter during local load testing if needed (`POST /api/v2/health/rate-limit` with `{"enabled": false}`), then run:
```bash
postman collection run postman/collections/marketmind-web-rag \
  -e postman/environments/local-eval.environment.yaml \
  -i "Web RAG Retrieval (Debug)" \
  -d evals/postman_queries.json --no-report-events

postman performance run postman/collections/marketmind-web-rag-perf \
  -e postman/environments/local-eval.environment.yaml \
  --data-file evals/postman_queries.json \
  --load-profile fixed --peak-vu 3 --duration 1 --output ndjson
```
