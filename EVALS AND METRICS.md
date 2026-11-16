# MarketMind Web RAG Evaluation Report

**Date:** 2026-11-16  
**Branch:** `evaluation-metrics`  
**Target API:** `POST /api/v2/rag/web` ([rag.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/app/api/v2/endpoints/rag.py))  
**Core Service:** `WebRAGService` ([web_rag.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/app/services/web_rag.py))

> **Environment Scope & Unverified Components:**  
> `GEMINI_API_KEY`, `SERPER_API_KEY`, and `BRAVE_API_KEY` are not configured in this checkout (no `.env` file present). Consequently:
> - **Latency runs** measure the **live retrieval pipeline** (`retrieval_only=true`: `QueryAnalyzer` heuristic fallback + DuckDuckGo search + Trafilatura scraping + `FreshnessReranker` + YFinance live quotes) and **exclude** Gemini LLM synthesis (`llm_ttft_ms`, `llm_total_ms`) and LanceDB embedding lookups (`cache_hit` = `false` across all runs).
> - **Recall@k runs** evaluate the **lexical and freshness retrieval stages** (`pre_filter_citations`, `BM25Reranker`, `FreshnessReranker`, and the production two-stage funnel). `HybridReranker` dense cosine scoring requires `GEMINI_API_KEY` and was not evaluated (`hybrid_reranker_evaluated: false`).
> - Local load tests disabled the IP sliding-window rate limiter (`25 req/min` default) via `POST /api/v2/health/rate-limit`.

---

## 1. Executive Summary

| Category | Metric | Value | Scope / Source |
|---|---|---:|---|
| **Postman Load Test (3 VUs)** | **p95 Response Time** | **`8,227 ms`** | 32 requests over 68s ([postman_perf.ndjson](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/postman_perf.ndjson)) |
| **Postman Load Test (3 VUs)** | **p90 / p99 / Avg** | `8,056` / `8,543` / `5,288 ms` | 0% errors, 0 failed assertions, `0.47 req/s` |
| **Python Stage Benchmark** | **HTTP p50 / p95 / p99** | `5,997.88` / **`11,749.56`** / `12,516.02 ms` | All 20 queries, `concurrency=1` ([latency_results.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/latency_results.json)) |
| **Python Stage Benchmark** | **Retrieval p50 / p95 (19 executed)** | `5,982.84` / **`11,763.35 ms`** | Excludes 1 heuristic guardrail refusal (`1.07 ms`) |
| **Scrape Reliability** | **URL Scrape Success Rate** | **`74.74%`** (`71 / 95`) | 19 executed queries × 5 target URLs |
| **Recall@5 ($N = 98$ docs)** | **`BM25Reranker`** | **`0.4631`** (`Hit@5 = 1.0000`, `MRR = 1.0000`) | 16 queries, 340 passages ([recall_results.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/recall_results.json)) |
| **Recall@5 ($N = 98$ docs)** | **`FreshnessReranker` (default)** | **`0.3810`** (`Hit@5 = 1.0000`, `MRR = 0.9062`) | 16 queries, 340 passages |
| **Recall@5 ($N = 98$ docs)** | **Production Two-Stage Funnel** | **`0.3552`** (`Hit@5 = 1.0000`, `MRR = 0.9375`) | Pre-filter top 5 URLs $\rightarrow$ chunk $\rightarrow$ freshness rerank |
| **Postman Functional Suite** | **Assertions Passed** | **`59 / 60`** (`98.3%`) | 20 queries; 1 failure exposed guardrail false negative |
| **Backend Pytest Suite** | **Tests Passed** | **`38 / 38`** (`15.97 s`) | Full suite after final edits |

---

## 2. Postman CLI API & Performance Metrics

### 2.1 Postman Performance Run (`postman performance run`)
* **Collection:** [marketmind-web-rag-perf](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/postman/collections/marketmind-web-rag-perf/.resources/definition.yaml)
* **Environment:** [local-eval.environment.yaml](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/postman/environments/local-eval.environment.yaml)
* **Data File:** [postman_queries.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/postman_queries.json) (20 queries)
* **Runner & Profile:** `local`, `fixed` profile, `3` virtual users, `1` minute configured (`68 s` actual completion)
* **Raw Output:** [postman_perf.ndjson](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/postman_perf.ndjson)

| Metric | Value |
|---|---:|
| Total Requests (`totalRequests`) | `32` |
| Duration (`durationSeconds`) | `68 s` |
| Virtual Users (`virtualUsers.avg`) | `3` |
| Request Throughput (`requestThroughput.rate`) | `0.47 req/s` |
| Average Response Time (`avg`) | `5,288 ms` |
| Minimum Response Time (`min`) | `38 ms` |
| p90 Response Time (`percentile90`) | `8,056 ms` |
| **p95 Response Time (`percentile95`)** | **`8,227 ms`** |
| p99 Response Time (`percentile99`) | `8,543 ms` |
| Maximum Response Time (`max`) | `8,543 ms` |
| HTTP / Transport / Script Error Rate | `0%` (`0` transport, `0` script errors) |
| Failed Test Assertions (`testFailures`) | `0%` (`0 / 32` requests) |

*(Note: `testFailures` in the performance collection checked HTTP `200` and `stage_timings.retrieval_total_ms > 0`; it did not assert `sources.length > 0`.)*

### 2.2 Postman Functional Collection Runs (`postman collection run`)

1. **Health Check** (`-i "Health Check"`, 1 iteration):
   * `GET http://127.0.0.1:8000/api/v2/health` $\rightarrow$ `200 OK`, `361 B`, **`106 ms`** (`808 ms` total CLI run).
   * Assertions: `2 / 2` passed (`Status code is 200`, `Database is healthy`).
2. **Web RAG Retrieval (Debug)** (`-i "Web RAG Retrieval (Debug)"`, 20 iterations across [postman_queries.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/postman_queries.json)):
   * Executed: `20` iterations, `20` requests, `20` test-scripts, `60` assertions (`59` passed, **`1` failed**).
   * Total run duration: `1 m 50.2 s` | Total data received: `298.51 KB` (~`14.9 KB/req`).
   * Response time summary: **avg `5.4 s`**, **min `39 ms`**, **max `11.3 s`**, **s.d. `2.1 s`**.
   * **Single Assertion Failure (Iteration 18):** `"AMD AI GPU MI300 data center competition"` returned `200 OK` (`971 B`, `39 ms`) with `sources.length === 0`, failing `Retrieval returned sources or passages` (`expected +0 to be above +0`) because `QueryAnalyzer._heuristic_fallback` classified the query as non-financial when Gemini structured analysis was unavailable.

---

## 3. Stage-by-Stage Pipeline Latency Breakdown

Measured sequentially (`concurrency=1`) via [benchmark_latency.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/benchmark_latency.py) and persisted in [latency_results.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/latency_results.json).

### 3.1 Percentile Breakdown — All 20 Queries

| Stage / Metric | Count | Min (ms) | Mean (ms) | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Max (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **HTTP End-to-End (`http_ms`)** | 20 | 56.93 | 6,398.04 | 5,997.88 | 9,784.63 | **11,749.56** | 12,516.02 | 12,707.64 |
| **Pipeline Retrieval (`retrieval_total_ms`)** | 20 | 1.07 | 6,368.13 | 5,976.27 | 9,758.58 | **11,718.03** | 12,406.93 | 12,579.16 |
| `query_analysis_ms` (heuristic fallback) | 20 | 0.49 | 0.81 | 0.73 | 1.21 | 1.24 | 1.54 | 1.61 |
| `cache_lookup_ms` (LanceDB error short-circuit) | 20 | 0.00 | 0.13 | 0.14 | 0.18 | 0.19 | 0.21 | 0.21 |
| `search_ms` (DuckDuckGo 3 sub-queries) | 20 | 0.00 | 3,494.73 | 3,639.14 | 4,565.52 | 4,692.30 | 5,264.80 | 5,407.93 |
| `pre_filter_ms` (`FreshnessReranker.pre_filter_citations`) | 20 | 0.00 | 1.32 | 1.10 | 1.78 | 2.79 | 4.05 | 4.36 |
| `scrape_ms` (`TrafilaturaWebScraper.scrape_many`) | 20 | 0.00 | 2,861.90 | 2,247.70 | 4,867.71 | 8,181.40 | 8,844.96 | 9,010.85 |
| `chunk_extract_ms` (400w / 50w overlap, cap 8) | 20 | 0.00 | 1.45 | 1.08 | 3.17 | 4.00 | 4.30 | 4.37 |
| `rerank_ms` (`FreshnessReranker.rerank`) | 20 | 0.00 | 6.15 | 5.22 | 11.79 | 12.56 | 13.04 | 13.16 |
| `quote_ms` (`YFinanceMarketClient.get_quote`, incl. non-ticker 0s) | 20 | 0.00 | 4,087.52 | 5,285.99 | 6,516.41 | 7,179.51 | 11,498.14 | 12,577.80 |

### 3.2 Retrieval-Executed Subset (19 Queries — Excluding Guardrail Refusal)

| Metric | Count | Min (ms) | Mean (ms) | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Max (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **`http_ms`** | 19 | 4,639.60 | 6,731.78 | 6,002.77 | 9,997.35 | **11,799.98** | 12,526.11 | 12,707.64 |
| **`retrieval_total_ms`** | 19 | 4,617.30 | 6,703.24 | 5,982.84 | 9,971.26 | **11,763.35** | 12,416.00 | 12,579.16 |
| **`search_ms`** | 19 | 1,832.72 | 3,678.66 | 3,726.00 | 4,575.42 | 4,729.97 | 5,272.34 | 5,407.93 |
| **`scrape_ms`** | 19 | 846.15 | 3,012.53 | 2,332.24 | 5,231.04 | 8,225.05 | 8,853.69 | 9,010.85 |
| **`quote_ms` (ticker queries only)** | 13 | 4,616.14 | 6,288.49 | 5,967.99 | 6,811.17 | 9,168.35 | 11,895.91 | 12,577.80 |

### 3.3 Retrieval Funnel Metrics

| Funnel Stage | Mean (All 20 Queries) | Mean (19 Executed Queries) | Total Across Run |
|---|---:|---:|---:|
| Search Candidates Found (`candidates_found`) | `13.55` | `14.26` | `271` |
| Target URLs Sent to Scraper (`urls_scraped`) | `4.75` | `5.00` | `95` |
| Successful Scrapes (`scrape_success_count`) | `3.55` | `3.74` | `71` (**`74.74%`** success) |
| Candidate Passages Extracted (`passages_extracted`) | `11.90` | `12.53` | `238` |
| Final Passages Selected (`passages_selected`) | `4.45` | `4.68` | `89` |

### 3.4 Per-Query Latency & Funnel Log (All 20 Queries)

| # | Country | Query | HTTP (ms) | Search (ms) | Scrape (ms) | Rerank (ms) | Quote (ms) | Candidates | Scraped OK | Passages Sel/Ext |
|---:|:---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | US | Nvidia data center revenue earnings outlook | 12,707.64 | 3,552.29 | 9,010.85 | 5.49 | 12,577.80 | 18 | 3/5 | 5/10 |
| 1 | IN | Reliance Industries quarterly results retail telecom | 6,161.90 | 3,954.60 | 2,163.17 | 11.71 | 6,135.96 | 12 | 5/5 | 5/20 |
| 2 | US | Federal Reserve interest rate decision inflation | 6,641.69 | 4,654.64 | 1,938.12 | 4.13 | 0.00 | 12 | 4/5 | 5/14 |
| 3 | IN | TCS Q2 earnings operating margin deal pipeline | 6,422.20 | 4,362.44 | 2,034.40 | 4.78 | 6,404.07 | 11 | 4/5 | 5/10 |
| 4 | US | Apple iPhone sales growth services revenue | 5,415.13 | 3,550.58 | 1,837.37 | 4.96 | 5,396.35 | 18 | 3/5 | 5/10 |
| 5 | IN | HDFC Bank net profit NIM asset quality | 4,639.60 | 3,766.51 | 846.15 | 1.39 | 4,616.14 | 6 | 1/5 | 2/2 |
| 6 | US | Tesla vehicle deliveries automotive gross margin | 5,636.71 | 4,470.10 | 1,134.63 | 4.72 | 5,612.98 | 18 | 3/5 | 4/18 |
| 7 | IN | RBI monetary policy repo rate inflation forecast | 5,154.44 | 3,190.26 | 1,935.92 | 7.95 | 0.00 | 18 | 5/5 | 5/16 |
| 8 | US | Microsoft Azure AI cloud growth capex | 5,198.93 | 4,009.41 | 1,158.02 | 4.42 | 5,175.62 | 11 | 3/5 | 4/8 |
| 9 | IN | Infosys revenue guidance AI transformation deals | 5,992.98 | 4,555.62 | 1,405.85 | 3.47 | 5,967.99 | 12 | 4/5 | 5/8 |
| 10 | US | Alphabet Google search advertising cloud earnings | 5,076.24 | 2,493.03 | 2,544.33 | 8.32 | 5,052.10 | 18 | 4/5 | 5/15 |
| 11 | IN | State Bank of India SBI loan growth treasury | 6,500.45 | 3,726.00 | 2,736.36 | 7.68 | 6,474.30 | 15 | 5/5 | 5/17 |
| 12 | US | Amazon AWS cloud operating income retail margin | 6,921.76 | 2,375.02 | 4,504.37 | 12.53 | 6,895.39 | 18 | 3/5 | 5/10 |
| 13 | IN | ICICI Bank net interest income deposit growth | 5,481.83 | 1,832.72 | 3,619.70 | 4.09 | 5,459.56 | 9 | 4/5 | 5/12 |
| 14 | US | Crude oil Brent prices OPEC supply outlook | 5,195.62 | 2,830.27 | 2,332.24 | 7.79 | 0.00 | 16 | 5/5 | 5/18 |
| 15 | IN | Gold price rally central bank demand outlook | 7,482.86 | 4,108.36 | 3,329.15 | 13.16 | 0.00 | 6 | 3/5 | 5/15 |
| 16 | IN | Nifty 50 Sensex FII DII institutional flows | 9,571.91 | 5,407.93 | 4,127.17 | 5.65 | 0.00 | 17 | 5/5 | 5/18 |
| 17 | US | AMD AI GPU MI300 data center competition | 56.93 | 0.00 | 0.00 | 0.00 | 0.00 | 0 | 0/0 | 0/0 |
| 18 | IN | Tata Motors JLR EV sales margin outlook | 6,002.77 | 3,528.39 | 2,442.50 | 7.22 | 5,982.05 | 18 | 4/5 | 5/12 |
| 19 | US | US Treasury 10 year yield bond market | 11,699.13 | 3,526.43 | 8,137.74 | 3.47 | 0.00 | 18 | 3/5 | 4/5 |

---

## 4. Retrieval Quality Across $N$ Documents (Recall@k, HitRate@k, MRR)

### 4.1 Evaluation Setup
* **Corpus:** [corpus.jsonl](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/corpus.jsonl) — **98 real scraped financial web articles** (`word_count >= 80`) harvested from 150 DuckDuckGo candidate URLs via `TrafilaturaWebScraper`.
* **Ground Truth (`qrels`):** [queries_with_qrels.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/queries_with_qrels.json) — **16 financial queries** with entity + multi-term topical relevance labels (`3` to `19` relevant docs per query; `14` queries fit at $N=25, 50$ and `16` queries at $N=75, 98$).
* **Production Parameters Tested:** `RAG_CHUNK_SIZE=400`, `RAG_CHUNK_OVERLAP=50`, `max_chunks_per_doc=8`, `MAX_SCRAPED_SOURCES=5`, `max_per_domain=2`, `RAG_HALF_LIFE_DAYS=7.0`, `RAG_RELEVANCE_FLOOR=0.25`.

### 4.2 Full Results Table ($N = 25, 50, 75, 98$)

| $N$ Docs | Passages | Queries | Method | Recall@1 | Recall@3 | Recall@5 | Recall@10 | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **25** | 110 | 14 | `pre_filter_citations` | 0.1906 | 0.3276 | 0.3937 | 0.6745 | 0.5714 | 0.5714 | 0.5714 | 0.8571 | 0.6133 |
| **25** | 110 | 14 | `bm25_reranker` | 0.3477 | 0.6502 | 0.7306 | 0.8320 | 0.7857 | 1.0000 | 1.0000 | 1.0000 | 0.8810 |
| **25** | 110 | 14 | `freshness_reranker` | 0.4227 | 0.5383 | 0.6425 | 0.7819 | 0.7857 | 1.0000 | 1.0000 | 1.0000 | 0.8810 |
| **25** | 110 | 14 | `production_two_stage_funnel` | 0.1727 | 0.2680 | 0.3157 | 0.3872 | 0.5000 | 0.5714 | 0.5714 | 0.5714 | 0.5357 |
| **50** | 213 | 14 | `pre_filter_citations` | 0.1962 | 0.3720 | 0.4565 | 0.6215 | 0.8571 | 0.9286 | 0.9286 | 0.9286 | 0.8946 |
| **50** | 213 | 14 | `bm25_reranker` | 0.2319 | 0.4663 | 0.5639 | 0.6918 | 0.9286 | 1.0000 | 1.0000 | 1.0000 | 0.9643 |
| **50** | 213 | 14 | `freshness_reranker` | 0.2891 | 0.4020 | 0.5210 | 0.6786 | 0.9286 | 1.0000 | 1.0000 | 1.0000 | 0.9643 |
| **50** | 213 | 14 | `production_two_stage_funnel` | 0.2176 | 0.3127 | 0.3577 | 0.4313 | 0.8571 | 0.9286 | 0.9286 | 0.9286 | 0.8929 |
| **75** | 276 | 16 | `pre_filter_citations` | 0.1681 | 0.3641 | 0.4838 | 0.6577 | 0.8125 | 1.0000 | 1.0000 | 1.0000 | 0.8958 |
| **75** | 276 | 16 | `bm25_reranker` | 0.2146 | 0.4420 | 0.5502 | 0.7119 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| **75** | 276 | 16 | `freshness_reranker` | 0.1677 | 0.3721 | 0.4956 | 0.6522 | 0.8750 | 1.0000 | 1.0000 | 1.0000 | 0.9375 |
| **75** | 276 | 16 | `production_two_stage_funnel` | 0.1677 | 0.3066 | 0.3938 | 0.4684 | 0.8750 | 1.0000 | 1.0000 | 1.0000 | 0.9375 |
| **98** | 340 | 16 | `pre_filter_citations` | 0.0811 | 0.2742 | 0.4251 | 0.6301 | 0.6875 | 1.0000 | 1.0000 | 1.0000 | 0.8333 |
| **98** | 340 | 16 | `bm25_reranker` | 0.1317 | 0.3169 | 0.4631 | 0.6817 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| **98** | 340 | 16 | `freshness_reranker` | 0.1046 | 0.2534 | 0.3810 | 0.5966 | 0.8125 | 1.0000 | 1.0000 | 1.0000 | 0.9062 |
| **98** | 340 | 16 | `production_two_stage_funnel` | 0.1135 | 0.2282 | 0.3552 | 0.4136 | 0.8750 | 1.0000 | 1.0000 | 1.0000 | 0.9375 |

*(Upper-bound note: at $N=98$, each query averages `9.625` relevant documents (`154 / 16`), so any $k=5$ passage cutoff has a theoretical macro-recall ceiling below `1.0`; `Hit@3` and `Hit@5` reach `1.0000` across all methods at $N=75$ and $N=98$.)*

---

## 5. Verification & Quality Checks

* **Pytest Suite:** `.\.venv\Scripts\python.exe -m pytest -q` $\rightarrow$ **`38 passed in 15.97s`** (35 existing tests + 3 new tests in [test_web_rag_debug.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/tests/test_web_rag_debug.py)).
* **Postman Schema Linting:**
  * `postman collection lint postman/collections/marketmind-web-rag` $\rightarrow$ `Scanned: 3 | Errors: 0 | Warnings: 0`
  * `postman collection lint postman/collections/marketmind-web-rag-perf` $\rightarrow$ `Scanned: 1 | Errors: 0 | Warnings: 0`
  * `postman environment lint postman/environments/local-eval.environment.yaml` $\rightarrow$ `Scanned: 1 | Errors: 0 | Warnings: 0`

---

## 6. Key Findings & Bottlenecks Identified

1. **Scrape & Quote Tail Latency Dominate p95:** Pure Python chunking/filtering/reranking takes `< 13 ms` at p95, whereas Trafilatura scraping (`8.23 s` p95 vs. the `1.2 s` design claim in `README.md`) and YFinance `get_quote` (`9.17 s` p95 across ticker queries, `12.58 s` max) drive the `11.76 s` retrieval p95.
2. **Heuristic Guardrail False Negative Without Gemini:** `QueryAnalyzer._heuristic_fallback` rejected `"AMD AI GPU MI300 data center competition"` because `"amd"` is absent from `COMMON_TICKERS` and `"ai"` / `"gpu"` / `"data center"` are not in `FINANCIAL_KEYWORDS`.
3. **Two-Stage Pre-Filter Bottleneck:** Pre-filtering $N=98$ candidates down to `MAX_SCRAPED_SOURCES=5` before passage reranking drops Recall@5 from `0.4631` (pure BM25) and `0.3810` (`FreshnessReranker`) to `0.3552` (`production_two_stage_funnel`), and limits `Recall@10` to `0.4136`.
4. **Freshness Decay Trade-off on Relevance:** At $N=98$, multiplying BM25 scores by rational time-decay (`half_life_days=7.0`, `relevance_floor=0.25`) lowers `Recall@5` from `0.4631` (`bm25_reranker`) to `0.3810` (`freshness_reranker`) and `MRR` from `1.0000` to `0.9062`, because newer or undated articles outrank older highly relevant articles.
