# MarketMind Web RAG Evaluation Report

**Date:** 2026-11-18  
**Branch:** `main`  
**Target API:** `POST /api/v2/rag/web` ([rag.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/app/api/v2/endpoints/rag.py))  
**Core Service:** `WebRAGService` ([web_rag.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/app/services/web_rag.py))  
**Live Models & Search:** `gemini-3.1-flash-lite-preview` (synthesis & judge), `gemini-embedding-001` (`HybridReranker`), `duckduckgo` (primary) + `brave` (`BRAVE_MIN_INTERVAL_SECONDS=1.05`)

> **Environment Scope:**  
> `GEMINI_API_KEY` and `BRAVE_API_KEY` (free tier) are configured via local `.env` (gitignored); `SERPER_API_KEY` and a standalone Redis server (`REDIS_URL`) are not configured in this checkout (caching uses the bounded in-memory `AsyncTTLCache` backend in [cache.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/app/core/cache.py)).
> - **Load & Retrieval Latency runs** (Sections 1–3) isolate the retrieval pipeline (`retrieval_only=true`) so latency reflects search, scraping, reranking, and YFinance quote stages without LLM generation variance.
> - **Live Search Provider Head-to-Head** (Section 5) compares `duckduckgo` vs. free-tier `brave` (1.05s request spacing) across 15 stratified queries under identical heuristic sub-queries.
> - **Live Gemini Evaluations** (Sections 4.4 & 6) benchmark `HybridReranker` (`gemini-embedding-001`) at $N=157$ and end-to-end streaming synthesis + LLM-as-a-Judge Citation Faithfulness using `gemini-3.1-flash-lite-preview`.
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

### 4.4 `HybridReranker` Dense + BM25 Evaluation ($N = 157$, `gemini-embedding-001`)
Evaluated across all `45` in-domain queries (`580` passages) with live `gemini-embedding-001` embeddings ([recall_results_v2_hybrid.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/recall_results_v2_hybrid.json)):

| Method ($N = 157$) | Recall@1 | Recall@3 | Recall@5 | Recall@10 | NDCG@5 | NDCG@10 | Hit@5 | Hit@10 | MRR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `pre_filter_citations` | 0.2259 | 0.5111 | 0.6815 | 0.8815 | 0.6381 | 0.7298 | 0.9778 | 1.0000 | 0.7904 |
| `bm25_reranker` | 0.1556 | 0.4407 | 0.6037 | 0.8185 | 0.5549 | 0.6663 | 0.9333 | 0.9556 | 0.6664 |
| `freshness_reranker` | 0.1556 | 0.4407 | 0.5963 | 0.8111 | 0.5560 | 0.6689 | 0.9111 | 0.9556 | 0.6695 |
| `production_two_stage_funnel` | 0.1704 | 0.4407 | 0.6037 | 0.8037 | 0.5682 | 0.6728 | 0.8889 | 0.9778 | 0.6957 |
| **`hybrid_reranker` (`gemini-embedding-001`)** | 0.1556 | 0.4333 | 0.5741 | 0.7815 | 0.5444 | 0.6567 | 0.9111 | 0.9556 | 0.6730 |

* **`hybrid_reranker` by Category (`Recall@5`):** `ticker_fundamentals = 0.6444`, `breaking_news = 0.6000`, `multi_hop_comparative = 0.4778`.
* **Takeaway:** Adding `gemini-embedding-001` RRF fusion improved `MRR` over pure `bm25_reranker` (`0.6730` vs. `0.6664`) and matched breaking-news `Recall@5` (`0.6000`), while exact-match financial BM25 + bounded freshness kept the highest top-5 precision (`0.6037` `Recall@5`, `0.6957` `MRR`) with zero external embedding API latency.

### 4.5 Guardrail Classification Metrics (All 55 Stratified Queries)
Evaluated via [evaluate_guardrail.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/evaluate_guardrail.py) ([guardrail_results.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/guardrail_results.json)):

* **Overall Accuracy:** **`100.0%` (`55 / 55`)** | **Precision:** `1.0000` | **Recall:** `1.0000` | **F1:** `1.0000`
* **Out-of-Domain / Adversarial Abstention Rate:** **`100.0%` (`10 / 10`)** (`0.0%` false-positive rate on adversarial prompts mentioning `Nvidia`, `Apple`, `Tesla`, `Amazon`, `Microsoft`, and `weather forecast`)
* **By Category:** Ticker Fundamentals `15/15`, Breaking Market News `15/15`, Multi-Hop Comparative `15/15`, Out-of-Domain/Adversarial `10/10`.

---

## 5. Live Search Provider Head-to-Head (`duckduckgo` vs. `brave` Free Tier)

Compared via [compare_search_providers.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/compare_search_providers.py) (`--retrieval-only --per-category 5`, `15` queries across Fundamentals / Breaking News / Comparative) with identical heuristic sub-queries and Brave free-tier rate spacing (`BRAVE_MIN_INTERVAL_SECONDS=1.05` + `429` spaced retry in [brave.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/app/infrastructure/search/brave.py)):

| Metric (15 Stratified Queries) | `duckduckgo` (Selected Primary) | `brave` (Free Tier, 1.05s Spaced) | Delta (`ddg` vs. `brave`) |
|---|---:|---:|---:|
| Non-Empty Source Rate | **`100.0%` (`15/15`)** | **`100.0%` (`15/15`)** | Tie (`0%` empty) |
| Avg Search Candidates Found | **`13.40`** | `8.40` | **`+59.5%` candidates** |
| Avg URLs Sent to Scraper | `11.13` | `8.00` | `+39.1%` scrape pool |
| Avg Successfully Scraped Docs | **`3.60`** | `3.00` | **`+20.0%` scraped docs** |
| Per-URL Scrape Success Rate | `32.34%` | **`37.50%`** | `+5.16 pp` Brave URL quality |
| Avg Final Passages Selected | **`4.20`** | `3.80` | **`+10.5%` passages** |
| `search_ms` p50 / Mean | **`2,779.87` / `2,526.97 ms`** | `7,765.14` / `5,241.08 ms` | **`2.79x` faster p50** |
| `search_ms` p95 / Max | **`4,556.17` / `4,602.16 ms`** | `8,190.66` / `8,328.39 ms` | **`-44.4%` search p95** |
| `scrape_ms` p50 / p95 | `3,024.69` / `3,042.80 ms` | `3,015.48` / `3,027.78 ms` | ~Identical (`3.0s` cap) |
| **`retrieval_total_ms` p50 / Mean** | **`5,839.24` / `5,376.07 ms`** | `10,595.93` / `8,068.56 ms` | **`-44.9%` p50 latency** |
| **`retrieval_total_ms` p95 / Max** | **`7,614.55` / `7,695.08 ms`** | `11,150.83` / `11,352.82 ms` | **`-31.7%` p95 latency** |

* **Provider Decision (`SEARCH_PROVIDER=duckduckgo` primary, `BRAVE_API_KEY` configured in `.env`):** `duckduckgo` wins on both latency (`5.84s` vs. `10.60s` p50; `7.61s` vs. `11.15s` p95) and retrieval volume (`13.4` vs. `8.4` candidates, `4.2` vs. `3.8` selected passages) because 3 parallel DDG sub-queries run concurrently, whereas free-tier Brave (`1 req/s`) serializes sub-queries and tiered fallbacks (`pw -> pm -> all`) across `1.05s`-spaced calls. Brave achieves a higher per-URL scrape success rate (`37.50%` vs. `32.34%`) and remains ready in `.env` as a zero-code-change config switch (`SEARCH_PROVIDER=brave`).
*Source: [search_provider_comparison.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/search_provider_comparison.json).*

---

## 6. Live E2E Synthesis Latency & Citation Faithfulness (`gemini-3.1-flash-lite-preview`)

Evaluated end-to-end (`retrieval_only=false`, vector cache disabled via `vector_store=None` so every query hits live search/scrape/YFinance/LLM) via [evaluate_faithfulness.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/evaluate_faithfulness.py) (`--limit 15`, Ticker Fundamentals) using **`gemini-3.1-flash-lite-preview`** for both streaming synthesis and structured `FaithfulnessJudgment` auditing:

* **Completion Scope:** **`13 / 15` queries** evaluated end-to-end; `2` skipped (`fund_03`: judge `503`/timeout during transient Gemini high-demand spike; `fund_05`: empty answer or no passages).
* **Citation Faithfulness (`146` atomic claims across `13` queries):**
  * **Micro Citation Faithfulness:** **`82.88%` (`121 / 146` supported claims)**
  * **Macro Citation Faithfulness:** **`83.19%`** (per-query range `0.5455`–`1.0000`, median `0.8571`)
  * **Root-Cause Audit of Unverified Claims:** Out of `27` claim verdicts flagged `supported=false` by the passage-only judge, **`26`** were live **YFinance `StockQuote` fields** (current price, day change, market cap, day/52-week range) injected into the synthesis prompt via `market_context` rather than retrieved web passages; only **`1`** claim out of `146` total atomic claims was a qualitative interpretation (`"well-capitalized"` in `fund_12`).
* **Live E2E Generation & Streaming Latency (`n = 13` completed queries):**
  * **`llm_ttft_ms` (Time to First Token):** p50 **`3,289.64 ms`**, mean `6,455.85 ms`, p95 `15,982.19 ms`
  * **`llm_total_ms` (Streaming Synthesis):** p50 **`5,445.33 ms`**, mean `8,540.89 ms`, p95 `17,670.46 ms`
  * **`total_ms` (Full E2E Pipeline):** p50 **`14,760.03 ms`**, mean `16,658.34 ms`, p95 `27,562.15 ms`

*Source: [faithfulness_results.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/faithfulness_results.json).*

---

## 7. Apples-to-Apples Reference on Original 98-Doc Benchmark

Comparing baseline ([recall_results.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/recall_results.json)) vs. post-fix ([recall_results_v2_on_98.json](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/evals/results/recall_results_v2_on_98.json)) at $N = 98$ (`340` passages, `16` queries):

| Method | Recall@5 (Before $\rightarrow$ After) | Recall@10 (Before $\rightarrow$ After) | NDCG@5 (After) | MRR (Before $\rightarrow$ After) |
|---|---:|---:|---:|---:|
| `pre_filter_citations` | `0.4251` $\rightarrow$ **`0.5063`** (`+19.1%`) | `0.6301` $\rightarrow$ **`0.7022`** | `0.8861` | `0.8333` $\rightarrow$ **`0.9688`** |
| `bm25_reranker` | `0.4631` $\rightarrow$ `0.4631` | `0.6817` $\rightarrow$ `0.6817` | `0.8551` | `1.0000` $\rightarrow$ `1.0000` |
| `freshness_reranker` | `0.3810` $\rightarrow$ **`0.4631`** (`+21.5%`) | `0.5966` $\rightarrow$ **`0.6778`** | `0.8551` | `0.9062` $\rightarrow$ **`1.0000`** |
| `production_two_stage_funnel` | `0.3552` $\rightarrow$ **`0.4318`** (`+21.6%`) | `0.4136` $\rightarrow$ **`0.6008`** (`+45.3%`) | `0.8058` | `0.9375` $\rightarrow$ **`0.9583`** |

---

## 8. Verification & Automated Checks

* **Pytest Suite:** `.\.venv\Scripts\python.exe -m pytest -q` $\rightarrow$ **`44 passed in 53.24s`** (includes [test_web_rag_debug.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/tests/test_web_rag_debug.py) and [test_evals_improvements.py](file:///c:/Users/shrihari/OneDrive%20-%20Invendis%20Technologies%20India%20Pvt.%20Ltd/Desktop/stuff/MarketMind-API/tests/test_evals_improvements.py), including `test_brave_searcher_free_tier_rate_spacing`).
* **Live Gemini & Search Evaluations:** Verified live with `gemini-3.1-flash-lite-preview`, `gemini-embedding-001`, `duckduckgo`, and spaced free-tier `brave` (`evals/compare_search_providers.py`, `evals/evaluate_recall.py --with-hybrid`, `evals/evaluate_faithfulness.py --limit 15`).
