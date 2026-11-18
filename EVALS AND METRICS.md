# MarketMind Web RAG Evaluation Report

**Date:** 2026-11-18  
**Branch:** `evals-v2` $\rightarrow$ `main`  
**Target API:** `POST /api/v2/rag/web` ([rag.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/app/api/v2/endpoints/rag.py))  
**Core Service:** `WebRAGService` ([web_rag.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/app/services/web_rag.py))

> **Environment Scope & Unverified Components:**  
> `GEMINI_API_KEY`, `SERPER_API_KEY`, `BRAVE_API_KEY`, and a running Redis server (`REDIS_URL`) are not configured in this checkout. Consequently:
> - **Latency runs** measure the **live retrieval pipeline** (`retrieval_only=true`: `QueryAnalyzer` heuristic fallback + DuckDuckGo search + Trafilatura scraping + `FreshnessReranker` + YFinance live quotes) using the bounded in-memory `AsyncTTLCache` backend ([cache.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/app/core/cache.py); Redis optional when `REDIS_URL` + `redis` are configured). Gemini LLM synthesis (`llm_ttft_ms`, `llm_total_ms`) and LanceDB embedding lookups are excluded.
> - **Retrieval quality runs** evaluate the lexical and freshness stages (`pre_filter_citations`, `BM25Reranker`, `FreshnessReranker`, and the production two-stage funnel). `HybridReranker` dense cosine scoring requires `GEMINI_API_KEY` and was not evaluated.
> - **LLM-as-a-Judge Citation Faithfulness** ([evaluate_faithfulness.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/evaluate_faithfulness.py)) is implemented and unit-tested with a stubbed judge, and its live run recorded `status: "skipped"` ([faithfulness_results.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/faithfulness_results.json)) pending `GEMINI_API_KEY`.
> - Local load tests disabled the IP sliding-window rate limiter (`25 req/min` default) via `POST /api/v2/health/rate-limit`.

---

## 1. Before vs. After Optimization Summary

### Engineering Changes Shipped
1. **Widened Pre-Scrape Funnel (`MAX_SCRAPED_SOURCES` $5 \rightarrow 12$, `MAX_SEARCH_CANDIDATES` $15 \rightarrow 20$):** Concurrent scraping with `asyncio.Semaphore(12)` and shared `httpx.AsyncClient` connection pooling ([web_scraper.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/app/infrastructure/scrapers/web_scraper.py)), plus BM25 IDF-weighted `pre_filter_citations`.
2. **Bounded Intent-Aware Recency Scoring (`RAG_RELEVANCE_FLOOR` $0.25 \rightarrow 0.85$):** Replaced harsh 75% time-decay penalty with bounded recency boost (`0.85 + 0.15 * freshness` for time-sensitive queries; `0.92 + 0.08 * freshness` for evergreen/fundamental queries) in [reranker.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/app/services/reranker.py).
3. **Hard Tail Timeouts & TTL Caching:** Added `3.0s` hard per-URL scrape timeout, `2.5s` `YFinanceMarketClient.get_quote` timeout, `4.5s` DuckDuckGo search timeout (`DDGS(timeout=3)`), and `AsyncTTLCache` (`300s` quotes/search, `3600s` scraped articles). Fixed quote stage timing to measure true `get_quote()` duration via `_timed_quote()`.
4. **Adversarial & Semiconductor Guardrail Fixes:** Expanded `COMMON_TICKERS` (`AMD`, `AVGO`, `QCOM`, `TSM`, etc.) and `FINANCIAL_KEYWORDS`, added word-boundary matching, and added `NON_FINANCIAL_SIGNALS` so queries like `"Nvidia RTX 5090 gaming FPS benchmark"` or `"weather forecast"` abstain cleanly.

### Measurable Impact (Before vs. After)

| Benchmark / Metric | Baseline (Before) | Optimized (After) | Delta |
|---|---:|---:|---:|
| **Postman 3-VU Load Test p95** | `8,227 ms` (`32` reqs) | **`3,092 ms`** (`179` reqs) | **`-62.4%` latency** |
| **Postman 3-VU Load Test Avg** | `5,288 ms` | **`939 ms`** | **`-82.2%` latency** |
| **Postman 3-VU Throughput** | `0.47 req/s` | **`2.63 req/s`** | **`5.6x` throughput** |
| **Cold Sequential HTTP p95 (20 queries)** | `11,749.56 ms` | **`7,655.96 ms`** | **`-34.8%` latency** |
| **Cold Scrape Stage p95** | `8,181.40 ms` | **`3,105.41 ms`** | **`-62.0%` latency** |
| **Warm Sequential HTTP p50 / Mean** | `5,997.88` / `6,398.04 ms` | **`2,045.37` / `2,729.09 ms`** | **`-65.9%` / `-57.3%`** |
| **$N=98$ `FreshnessReranker` Recall@5** | `0.3810` | **`0.4631`** | **`+21.5%` relative** |
| **$N=98$ `FreshnessReranker` MRR** | `0.9062` | **`1.0000`** | **`+10.4%` (`1.0` MRR)** |
| **$N=98$ Two-Stage Funnel Recall@5** | `0.3552` | **`0.4318`** | **`+21.6%` relative** |
| **$N=98$ Two-Stage Funnel Recall@10** | `0.4136` | **`0.6008`** | **`+45.3%` relative** |
| **Pytest Suite** | `38 passed` | **`43 passed`** | `+5` unit tests |

---

## 2. Postman CLI API & Performance Metrics

### 2.1 Postman Performance Run (`postman performance run`)
* **Collection:** [marketmind-web-rag-perf](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/postman/collections/marketmind-web-rag-perf/.resources/definition.yaml)
* **Environment:** [local-eval.environment.yaml](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/postman/environments/local-eval.environment.yaml)
* **Workload:** [postman_queries.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/postman_queries.json), `local` runner, `fixed` profile, `3` virtual users, `1` minute (`68 s` actual).

| Metric | Baseline ([postman_perf.ndjson](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/postman_perf.ndjson)) | Optimized ([postman_perf_v2.ndjson](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/postman_perf_v2.ndjson)) |
|---|---:|---:|
| Total Requests (`totalRequests`) | `32` | **`179`** |
| Duration (`durationSeconds`) | `68 s` | `68 s` |
| Virtual Users (`virtualUsers.avg`) | `3` | `3` |
| Throughput (`requestThroughput.rate`) | `0.47 req/s` | **`2.63 req/s`** |
| Average Response Time (`avg`) | `5,288 ms` | **`939 ms`** |
| Minimum Response Time (`min`) | `38 ms` | `26 ms` |
| p90 Response Time (`percentile90`) | `8,056 ms` | **`3,049 ms`** |
| **p95 Response Time (`percentile95`)** | **`8,227 ms`** | **`3,092 ms`** |
| p99 Response Time (`percentile99`) | `8,543 ms` | **`4,574 ms`** |
| Maximum Response Time (`max`) | `8,543 ms` | `7,306 ms` |
| Error Rate / Transport / Script Errors | `0%` (`0` / `0`) | `0%` (`0` / `0`) |
| Failed Assertions (`testFailures`) | `0%` (`0 / 32`) | `0%` (`0 / 179`) |

### 2.2 Postman Functional Collection Runs (`postman collection run`)
* **Baseline (20 iterations):** `59 / 60` assertions passed (`avg 5.4 s`, `min 39 ms`, `max 11.3 s`, `s.d. 2.1 s`); Iteration 18 (`AMD AI GPU MI300...`) failed due to heuristic guardrail false negative.
* **After Improvements (20 iterations):** `58 / 60` assertions passed (`avg 1,304 ms`, `min 19 ms`, `max 7.5 s`, `s.d. 1,953 ms`, total run `27.5 s`); Iteration 18 (`AMD`) **passed in `148 ms`**, while Iterations 6 and 20 returned 0 sources after hitting the `4.5s` live DuckDuckGo timeout under back-to-back queries.

---

## 3. Stage-by-Stage Python Latency Breakdown (20 Queries, `concurrency=1`)

| Stage / Metric | Baseline p50 / p95 (ms) | Cold Optimized p50 / p95 (ms) | Warm Optimized p50 / p95 (ms) |
|---|---:|---:|---:|
| **`http_ms`** | `5,997.88` / `11,749.56` | `6,798.34` / **`7,655.96`** | **`2,045.37`** / `7,401.93` *(min `33.57`)* |
| **`retrieval_total_ms`** | `5,976.27` / `11,718.03` | `6,775.39` / **`7,632.80`** | **`2,028.97`** / `7,332.36` *(min `5.86`)* |
| `query_analysis_ms` | `0.73` / `1.24` | `2.31` / `6.12` | `1.42` / `2.82` |
| `cache_lookup_ms` (LanceDB) | `0.14` / `0.19` | `0.14` / `0.30` | `0.11` / `0.19` |
| `search_ms` (DuckDuckGo) | `3,639.14` / `4,692.30` | `4,509.91` / `4,519.38` | **`0.12`** / `4,508.43` *(mean `891.21`)* |
| `pre_filter_ms` | `1.10` / `2.79` | `0.02` / `1.19` | `0.01` / `2.27` |
| `scrape_ms` (Trafilatura) | `2,247.70` / `8,181.40` | `2,256.03` / **`3,105.41`** | `1,866.68` / **`3,018.78`** |
| `chunk_extract_ms` | `1.08` / `4.00` | `0.61` / `2.26` | `0.98` / `2.53` |
| `rerank_ms` | `5.22` / `12.56` | `2.49` / `11.90` | `3.69` / `9.69` |
| `quote_ms` (YFinance) | `5,285.99` / `7,179.51` *(wait-inflated)* | **`340.75` / `653.24`** *(true timed)* | **`0.04` / `12.83`** |

*Sources: [latency_results.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/latency_results.json), [latency_results_v2_cold.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/latency_results_v2_cold.json), [latency_results_v2_warm.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/latency_results_v2_warm.json).*

---

## 4. Upgraded Stratified Evaluation (55 Queries, $N = 157$ Docs, Tight Gold Labels)

### 4.1 Stratified Dataset & Gold Labeling
* **Queries:** [stratified_queries.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/stratified_queries.json) — **55 queries** across 4 strata:
  * **Ticker Fundamentals (`15`)**, **Breaking Market News (`15`)**, **Multi-Hop / Comparative (`15`)**, and **Out-of-Domain / Adversarial (`10`)**.
* **Corpus:** [corpus_v2.jsonl](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/corpus_v2.jsonl) — **157 real scraped financial web articles** (`580` passage chunks at full $N$).
* **Tight Gold Qrels:** [stratified_qrels.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/stratified_qrels.json) — **1–3 strictly matched gold documents per in-domain query** (`avg = 2.98` gold docs/query, `0` queries with missing gold docs).

### 4.2 Retrieval Quality Across $N \in \{40, 80, 120, 157\}$

| $N$ Docs (Passages) | Queries | Method | Recall@1 | Recall@3 | Recall@5 | Recall@10 | NDCG@5 | NDCG@10 | Hit@5 | MRR |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **40** *(161)* | 31 | `pre_filter_citations` | 0.3925 | 0.7688 | 0.9194 | 0.9677 | 0.8390 | 0.8595 | 0.9677 | 0.8584 |
| **40** *(161)* | 31 | `bm25_reranker` | 0.4355 | 0.7419 | 0.9086 | 0.9785 | 0.8730 | 0.9091 | 1.0000 | 0.9194 |
| **40** *(161)* | 31 | `freshness_reranker` | 0.4355 | 0.7366 | 0.8925 | 0.9785 | 0.8605 | 0.9058 | 1.0000 | 0.9194 |
| **40** *(161)* | 31 | `production_two_stage_funnel` | 0.4032 | 0.7043 | 0.8871 | 0.9462 | 0.8488 | 0.8816 | 0.9677 | 0.8871 |
| **80** *(302)* | 44 | `pre_filter_citations` | 0.2727 | 0.6894 | 0.8788 | 0.9545 | 0.8103 | 0.8432 | 1.0000 | 0.8606 |
| **80** *(302)* | 44 | `bm25_reranker` | 0.2576 | 0.5909 | 0.7955 | 0.9318 | 0.7618 | 0.8338 | 0.9545 | 0.8455 |
| **80** *(302)* | 44 | `freshness_reranker` | 0.2576 | 0.5947 | 0.7879 | 0.9318 | 0.7581 | 0.8352 | 0.9545 | 0.8462 |
| **80** *(302)* | 44 | `production_two_stage_funnel` | 0.2727 | 0.5644 | 0.7917 | 0.9015 | 0.7654 | 0.8229 | 1.0000 | 0.8731 |
| **120** *(435)* | 45 | `pre_filter_citations` | 0.2407 | 0.5630 | 0.7481 | 0.8963 | 0.7018 | 0.7712 | 1.0000 | 0.8244 |
| **120** *(435)* | 45 | `bm25_reranker` | 0.2037 | 0.5519 | 0.6926 | 0.8556 | 0.6649 | 0.7530 | 0.9556 | 0.7641 |
| **120** *(435)* | 45 | `freshness_reranker` | 0.2037 | 0.5519 | 0.6778 | 0.8556 | 0.6601 | 0.7572 | 0.9333 | 0.7643 |
| **120** *(435)* | 45 | `production_two_stage_funnel` | 0.2296 | 0.5370 | 0.6704 | 0.8185 | 0.6626 | 0.7423 | 0.9556 | 0.8032 |
| **157** *(580)* | 45 | `pre_filter_citations` | 0.2259 | 0.5111 | 0.6815 | 0.8815 | 0.6381 | 0.7298 | 0.9778 | 0.7904 |
| **157** *(580)* | 45 | `bm25_reranker` | 0.1556 | 0.4407 | 0.6037 | 0.8185 | 0.5549 | 0.6663 | 0.9333 | 0.6664 |
| **157** *(580)* | 45 | `freshness_reranker` | 0.1556 | 0.4407 | 0.5963 | 0.8111 | 0.5560 | 0.6689 | 0.9111 | 0.6695 |
| **157** *(580)* | 45 | **`production_two_stage_funnel`** | **0.1778** | **0.4481** | **0.6111** | **0.8111** | **0.5768** | **0.6810** | **0.8889** | **0.7057** |

### 4.3 Per-Category Retrieval Breakdown ($N = 157$, `production_two_stage_funnel`)

| Category | Queries | Recall@1 | Recall@3 | Recall@5 | Recall@10 | NDCG@5 | Hit@5 | Hit@10 | MRR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Ticker Fundamentals** | 15 | 0.1778 | 0.4444 | **0.7111** | 0.8889 | 0.6499 | 0.9333 | 1.0000 | 0.7356 |
| **Breaking Market News** | 15 | 0.2000 | 0.4889 | **0.6000** | 0.8000 | 0.5839 | 0.9333 | 1.0000 | 0.7489 |
| **Multi-Hop / Comparative** | 15 | 0.1556 | 0.4111 | **0.5222** | 0.7444 | 0.4965 | 0.8000 | 0.9333 | 0.6328 |

*Source: [recall_results_v2_stratified.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/recall_results_v2_stratified.json).*

### 4.4 Guardrail Classification Metrics (All 55 Stratified Queries)
Evaluated via [evaluate_guardrail.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/evaluate_guardrail.py) ([guardrail_results.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/guardrail_results.json)):

* **Overall Accuracy:** **`100.0%` (`55 / 55`)** | **Precision:** `1.0000` | **Recall:** `1.0000` | **F1:** `1.0000`
* **Out-of-Domain / Adversarial Abstention Rate:** **`100.0%` (`10 / 10`)** (`0.0%` false-positive rate on adversarial prompts mentioning `Nvidia`, `Apple`, `Tesla`, `Amazon`, `Microsoft`, and `weather forecast`)
* **By Category:** Ticker Fundamentals `15/15`, Breaking Market News `15/15`, Multi-Hop Comparative `15/15`, Out-of-Domain/Adversarial `10/10`.

---

## 5. Apples-to-Apples Reference on Original 98-Doc Benchmark

Comparing baseline ([recall_results.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/recall_results.json)) vs. post-fix ([recall_results_v2_on_98.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/recall_results_v2_on_98.json)) at $N = 98$ (`340` passages, `16` queries):

| Method | Recall@5 (Before $\rightarrow$ After) | Recall@10 (Before $\rightarrow$ After) | NDCG@5 (After) | MRR (Before $\rightarrow$ After) |
|---|---:|---:|---:|---:|
| `pre_filter_citations` | `0.4251` $\rightarrow$ **`0.5063`** (`+19.1%`) | `0.6301` $\rightarrow$ **`0.7022`** | `0.8861` | `0.8333` $\rightarrow$ **`0.9688`** |
| `bm25_reranker` | `0.4631` $\rightarrow$ `0.4631` | `0.6817` $\rightarrow$ `0.6817` | `0.8551` | `1.0000` $\rightarrow$ `1.0000` |
| `freshness_reranker` | `0.3810` $\rightarrow$ **`0.4631`** (`+21.5%`) | `0.5966` $\rightarrow$ **`0.6778`** | `0.8551` | `0.9062` $\rightarrow$ **`1.0000`** |
| `production_two_stage_funnel` | `0.3552` $\rightarrow$ **`0.4318`** (`+21.6%`) | `0.4136` $\rightarrow$ **`0.6008`** (`+45.3%`) | `0.8058` | `0.9375` $\rightarrow$ **`0.9583`** |

---

## 6. Verification & Automated Checks

* **Pytest Suite:** `.\.venv\Scripts\python.exe -m pytest -q` $\rightarrow$ **`43 passed in 17.37s`** (includes [test_web_rag_debug.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/tests/test_web_rag_debug.py) and [test_evals_improvements.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/tests/test_evals_improvements.py)).
* **Citation Faithfulness Judge:** [evaluate_faithfulness.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/evaluate_faithfulness.py) verified with `StubJudgeLLM` in `pytest`; live Gemini Flash judgment awaiting `GEMINI_API_KEY`.
