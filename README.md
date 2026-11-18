# MarketMind API (v2)

[![FastAPI](https://img.shields.io/badge/FastAPI-v0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Gemini](https://img.shields.io/badge/Gemini-3.8_Flash-4285F4.svg?logo=google&logoColor=white)](https://ai.google.dev/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.x-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev/)

**MarketMind API** is an institutional-grade, full-stack financial intelligence application and API engine. Re-engineered from the ground up for strict **512 MB RAM footprint** and **$0 free-tier cloud deployment** (Render + Vercel + Neon/Supabase), MarketMind combines real-time equity market data, streaming Web RAG, native multimodal document analysis, keyless retail sentiment discovery, and downloadable institutional equity research reports.

---

## Repository Organization

Following the completion of the v2 modernization phase, the repository is organized into distinct, modular layers:

```
MarketMind-API/
├── app/                  # Modernized Clean Architecture backend (MarketMind API v2)
│   ├── api/              # RESTful route controllers & v2 master router
│   ├── core/             # Configuration, logging, database, and rate limiting
│   ├── domain/           # Business entities, Pydantic schemas, and abstract interfaces
│   ├── infrastructure/   # Pluggable adapters (Gemini, LanceDB, YFinance, Scrapers, Search)
│   └── services/         # Domain services (Web RAG, Document RAG, Reddit RAG, Dashboard, Research)
├── frontend/             # Modern web terminal (Vite, React 19, TypeScript, Tailwind CSS)
│   ├── src/              # React components, hooks, API clients, and theme styles
│   └── dist/             # Production build distribution (embeddable in FastAPI)
├── tests/                # Automated unit & integration tests (pytest + pytest-asyncio)
├── v1/                   #  Legacy Version 1 Archive (Prototypes, legacy files & original docs)
│   ├── api/              # Legacy API endpoints (Pinecone, ChromaDB, LangChain, Neo4j)
│   ├── streaming/        # Legacy streaming routes & socket handlers
│   ├── static/           # Legacy prototype HTML/JS user interface
│   ├── config.py         # Legacy configuration module
│   ├── disclaimer.py     # Legacy disclaimer constants
│   ├── token_logger.py   # Legacy token logger
│   ├── run_pipeline.py   # Legacy knowledge graph pipeline script
│   ├── run_financial_event_pipeline.py # Legacy financial event pipeline
│   ├── Developer Guide.md# Legacy v1 developer guide
│   └── README.md         # Legacy v1 README documentation
├── main.py               # Root application entrypoint (delegates to app.main:app)
├── Dockerfile            # Multi-stage production container build (Render-ready)
├── render.yaml           # Infrastructure-as-Code Blueprint for Render cloud service
├── requirements.txt      # Lean, categorized Python dependencies
├── pytest.ini            # Pytest configuration with automatic pythonpath resolution
└── DEVELOPER_GUIDE.md   # Comprehensive architecture and developer navigation guide
```

---

##  Features (v2)

- **Streaming Web RAG with Typed SSE & Recency Scoring**: Real-time multi-angle financial retrieval with candidate pre-filtering (15 -> 5 URLs), rational time-decay reranking ($S_{\text{rel}} \times S_{\text{fresh}}$), HTML metadata date extraction, and citation tracking (`status`, `sources`, `token`, `complete`).
- **Native Multimodal Document RAG**: Direct PDF ingestion leveraging Gemini's native 1M+ token context window—no heavy OCR, no vectorization bottlenecks, with visual balance sheet & chart analysis.
- **Live Market Dashboard (SWR Cached)**: Real-time benchmark indices (Nifty 50, Sensex, S&P 500, Nasdaq), standout gainers/losers, and AI daily macro briefs with Stale-While-Revalidate caching in PostgreSQL/SQLite.
- **Embedded LanceDB Semantic News Cache & Document Vault**: High-speed Apache Arrow columnar vector store running completely in-process (<30 MB RAM overhead).
- **Keyless Retail Community Sentiment**: Reddit discussion extraction via JSON endpoints without requiring paid Reddit API credentials.
- **Deep Equity Research & In-Memory PDF Export**: Automated 7-section institutional research generator producing downloadable PDF reports via ReportLab.
- **Sliding-Window IP Rate Limiter**: 25 req/min protection with dynamic runtime inspection endpoints (`/api/v2/health/rate-limit`).
- **Anonymous Device Sessions**: Multi-turn conversation persistence isolated by browser client UUID (`X-Client-ID`).

---

## Freshness-Aware Web RAG & Dynamic Recency Scoring

In financial intelligence, retrieving context from months or years ago (e.g. outdated quarterly earnings or stale guidance) directly degrades synthesis quality. MarketMind v2 employs a multi-tier freshness architecture that systematically prioritizes up-to-date sources:

```
[ Search: DDG / Brave / Serper ] (Fetch 15 Candidates, timelimit='w')
               │
               ▼
[ Pre-Scrape Date Extractor ] (ISO timestamps, URL regex, snippet dates)
               │
               ▼
[ Pre-Scrape Filter ] (Rank by Snippet BM25 × Freshness -> Select Top 5)
               │
               ▼
[ Trafilatura Scraper ] (Scrape ONLY top 5 URLs in parallel)
               │
               ▼
[ HTML Metadata Date Extractor ] (OpenGraph, JSON-LD, <time> tags)
               │
               ▼
[ Passage Chunking ] (Word chunks with elapsed time metadata)
               │
               ▼
[ FreshnessReranker ] (S_final = S_BM25 × (0.25 + 0.75 × Decay(Δt)))
               │
               ▼
[ Gemini Streaming Synthesis ] (Prompt with explicit 'Published: YYYY-MM-DD')
```

### Key Pillars of the Recency Engine

1. **Configurable Search Horizon with Tiered Fallback**:
   - Primary retrieval focuses on news feeds (`ddgs.news`, Brave News, Serper News) using `SEARCH_TIMELIMIT` (default: `'w'` for past week).
   - **Tiered fallback**: If a time-limited news search returns fewer than 3 results, it automatically expands to past month (`'m'`), then unconstrained search, preventing empty context on niche or conceptual queries.
   - Uniform provider mapping:
     - `'d'` (Past 24h): DuckDuckGo `d` | Brave `pd` | Google Serper `tbs=qdr:d`
     - `'w'` (Past week): DuckDuckGo `w` | Brave `pw` | Google Serper `tbs=qdr:w` *(Default)*
     - `'m'` (Past month): DuckDuckGo `m` | Brave `pm` | Google Serper `tbs=qdr:m`
     - `'y'` (Past year): DuckDuckGo `y` | Brave `py` | Google Serper `tbs=qdr:y`

2. **Pre-Scrape Filtering (Compute & Latency Optimization)**:
   - Instead of scraping 15–20 web pages, MarketMind retrieves 15 raw search snippets and pre-ranks them using **Snippet BM25 $\times$ Freshness Decay**.
   - Only the top `MAX_SCRAPED_SOURCES` (default: 5) URLs are scraped concurrently, keeping total scrape latency under 1.2s and conserving serverless memory.

3. **Multi-Tier Publication Date Extraction**:
   - **Pre-Scrape**: Captures native ISO dates from news APIs, URL date patterns (`/2026/09/28/`), and snippet prefix dates (`"Sep 28, 2026 — ..."`).
   - **Post-Scrape**: Trafilatura inspects HTML meta tags (OpenGraph `article:published_time`, JSON-LD `datePublished`, HTML5 `<time>`, and Dublin Core), syncing confirmed dates back to citations.
   - **Undated Pages**: Evergreen pages receive a neutral prior score ($0.35$), preventing them from being discarded if highly relevant, but ensuring fresh news always wins.

4. **Continuous Rational Decay Scoring**:
   - Rather than brittle keyword-matching (`"latest" in query`), every chunk is scored using a continuous heavy-tailed rational decay function:
     $$\text{Decay}(\Delta t) = \frac{1}{1 + \left(\frac{\Delta t}{\tau}\right)}$$
     where $\Delta t$ is the document age in days and $\tau = 7.0$ days (`RAG_HALF_LIFE_DAYS`).
   - Blended via multiplicative rank attenuation:
     $$S_{\text{final}} = S_{\text{relevance}} \times \left( \alpha + (1 - \alpha) \cdot \text{Decay}(\Delta t) \right)$$
     where $\alpha = 0.25$ (`RAG_RELEVANCE_FLOOR`).
   - **Safety Guarantee**: Irrelevant breaking articles ($S_{\text{rel}} = 0$) receive a score of $0$ regardless of freshness, while fresh relevant articles outrank older coverage by up to $4:1$.

5. **Chronologically Grounded Synthesis**:
   - Final context chunks injected into Gemini include explicit `Published: YYYY-MM-DD` timestamps.
   - System prompt instructions mandate prioritizing newer data when resolving conflicting earnings numbers, targets, or economic data across citations.

---

##  Quick Start

### 1. Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend development)
- Free Google AI Studio API key (`GEMINI_API_KEY`)

### 2. Backend Setup

```bash
# Clone the repository
git clone https://github.com/shrihari808/MarketMind-API.git
cd MarketMind-API

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and supply your GEMINI_API_KEY
```

### 3. Run the Backend

```bash
# Run with Uvicorn
uvicorn main:app --reload --port 8000
# or direct execution:
python main.py
```

FastAPI Interactive Docs will be accessible at: `http://localhost:8000/docs`

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The Web Terminal will be available at: `http://localhost:5173`

---

## Testing

MarketMind provides a comprehensive automated test suite spanning domain services, REST API endpoints, security middleware, and embedded vector storage.

### Running Backend Tests

Run the full test suite with `pytest`:

```bash
pytest
```

Run specific test modules:

```bash
# REST API Endpoints (Gateway, Health, Stocks, Dashboard, Reddit Sentiment, Chat Sessions)
pytest tests/test_api_endpoints.py

# Sliding-Window Rate Limiter & Security Middleware
pytest tests/test_rate_limiter.py

# Financial Query Intent Classification & Ticker Resolution
pytest tests/test_query_analyzer.py

# Anonymous Device Chat History & Context Persistence
pytest tests/test_chat_history.py

# Freshness-Aware BM25 Reranker & Rational Decay Scoring
pytest tests/test_freshness_reranker.py

# LanceDB Semantic News Caching & Historical Filings Vault
pytest tests/test_lance_cache_and_vault.py

# Yahoo Finance Market Data Client & Benchmark Fallbacks
pytest tests/test_yfinance_client.py
```

### Available Test Suites Overview

| Test Module | Coverage & Capabilities Tested |
|---|---|
| `test_api_endpoints.py` | FastAPI gateway welcome, health check probe, dynamic rate limit inspection & reconfiguration, stock quotes/fundamentals, SWR dashboard, Reddit sentiment validation, and session endpoints. |
| `test_rate_limiter.py` | Sliding-window calculation, threshold blocking (HTTP 429), `Retry-After` header accuracy, client IP isolation, runtime configuration overrides (`set_enabled`, `set_limit`), and path exemptions (`/api/v2/health`, `/docs`). |
| `test_query_analyzer.py` | Multi-turn conversational follow-up detection, financial keyword dictionary matching, automated Indian & US ticker detection, and structured query decomposition. |
| `test_chat_history.py` | SQLite message turn persistence, LLM prompt context tuples, session listing by update timestamp, cascade deletion, and device-level client UUID isolation. |
| `test_freshness_reranker.py` | Rational time-decay curve calculations ($S_{\text{rel}} \times S_{\text{fresh}}$), multi-format date extraction (ISO 8601, RFC 2822, relative times), and base domain diversification. |
| `test_lance_cache_and_vault.py` | Apache Arrow LanceDB vector lifecycle: semantic news caching with TTL expiration, corporate filing PDF/text chunking, page tracking, and cross-document RAG querying. |
| `test_yfinance_client.py` | Live equity quote fetching, valuation multiples (P/E, P/B, ROE), benchmark indices, gainer/loser sorting, and resilient baseline fallbacks. |
| `test_web_rag_debug.py` | `WebRAGService` per-stage timing diagnostics (`RAGStageTimings`), `retrieval_only` mode, and `X-RAG-Retrieval-Ms` / `X-RAG-Total-Ms` debug headers. |
| `test_evals_improvements.py` | `AsyncTTLCache` LRU/TTL eviction, bounded intent-aware `FreshnessReranker`, adversarial `QueryAnalyzer` abstention, scraper timeout/cache, and faithfulness judge schema. |

---

## Web RAG Evaluations & Performance Metrics

Comprehensive before/after latency, throughput, guardrail, and stratified retrieval-quality benchmarks for the Web RAG pipeline are recorded in **[`EVALS AND METRICS.md`](./EVALS%20AND%20METRICS.md)** (all evaluation scripts, Postman collections, and corpus artifacts live in [`evals/`](./evals/) and [`postman/`](./postman/)).

Key measured highlights *(see [`EVALS AND METRICS.md`](./EVALS%20AND%20METRICS.md) for full stage breakdowns, before/after tables, search-provider head-to-head, `N`-scaling metrics, and LLM-as-a-Judge faithfulness verdicts)*:

- **Postman Load Test (3 VUs, 68s, `179` requests):** **`3,092 ms` p95** (`939 ms` avg, `2.63 req/s`, `0%` errors) — down **62.4%** from the `8,227 ms` baseline (`32` reqs, `0.47 req/s`).
- **Stage-by-Stage Retrieval Latency (20 queries, sequential):** Cold retrieval p95 improved from `11,749.56 ms` to **`7,655.96 ms`** (`-34.8%`) via `3.0s` hard scraper timeouts (`scrape_ms` p95 `8,181 ms` $\rightarrow$ `3,105 ms`), `2.5s` quote timeouts (`quote_ms` p95 `653.24 ms`), and `4.5s` search caps; warm-cache runs drop `http_ms` p50 to **`2,045.37 ms`** (`min 33.57 ms`, `quote_ms p50 = 0.04 ms`).
- **Search Provider Comparison (`duckduckgo` vs. free-tier `brave`, 15 stratified queries):** Both hit `100%` non-empty sources; **`duckduckgo`** achieved **`44.9%` lower retrieval p50** (`5,839 ms` vs. `10,596 ms`) and `+59.5%` more candidates (`13.4` vs. `8.4`), while `brave` (1.05s rate-spaced) achieved a higher per-URL scrape rate (`37.50%` vs. `32.34%`). `duckduckgo` is set as default with `BRAVE_API_KEY` ready in `.env`.
- **Stratified Tight-Gold Retrieval (55 queries, $N = 157$ docs, `2.98` gold docs/query):**
  - **Production Two-Stage Funnel (`MAX_SCRAPED_SOURCES=12`):** `Recall@5 = 0.6111` (`0.7111` Fundamentals / `0.6000` Breaking News / `0.5222` Comparative), `NDCG@5 = 0.5768`, `Hit@5 = 0.8889`, `MRR = 0.7057`.
  - **`HybridReranker` (`gemini-embedding-001`, $N = 157$):** `Recall@5 = 0.5741` (`0.6444` Fundamentals / `0.6000` Breaking News), `MRR = 0.6730`, `Hit@5 = 0.9111`.
  - **Apples-to-Apples ($N = 98$):** Bounded intent-aware `FreshnessReranker` lifted `Recall@5` from `0.3810` $\rightarrow$ **`0.4631`** (`+21.5%`, `MRR = 1.0000`), and widened two-stage `Recall@5` rose from `0.3552` $\rightarrow$ **`0.4318`** (`+21.6%`, `Recall@10` `+45.3%`).
- **Live Gemini E2E Faithfulness & Guardrail (`gemini-3.1-flash-lite-preview`):**
  - **Citation Faithfulness (`13/15` completed queries, `146` claims):** **`82.88%` micro** (`121/146` claims) / **`83.19%` macro** (passage-only judge; `26/27` unverified verdicts were YFinance `StockQuote` fields outside web passages, `1/146` qualitative interpretation), with `llm_ttft_ms` p50 `3,289.64 ms`.
  - **Guardrail Classification (55 stratified queries):** **`100.0%` accuracy** (`45/45` in-domain + `10/10` OOD/adversarial abstention).

See **[`EVALS AND METRICS.md`](./EVALS%20AND%20METRICS.md)** for all detailed evaluation tables, LLM-as-a-Judge faithfulness setup, and reproduction instructions.

### Frontend Code Quality & Linting

```bash
cd frontend

# Run Oxlint for fast static analysis
npm run lint

# Run TypeScript typecheck & production bundle build
npm run build
```

---

## API Endpoints (v2)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API Gateway status or serves Web Terminal |
| `GET` | `/api/v2/health` | System health, provider statuses & DB latency |
| `GET` | `/api/v2/health/rate-limit` | Dynamic rate limiter status & configuration |
| `POST` | `/api/v2/rag/web` | Streaming Financial Web RAG with SSE |
| `POST` | `/api/v2/rag/document` | Multimodal PDF Document Q&A stream |
| `POST` | `/api/v2/rag/document/summary` | Executive summary generation for uploaded PDF |
| `POST` | `/api/v2/rag/reddit` | Retail community sentiment & thesis analysis |
| `GET` | `/api/v2/dashboard` | Live market indices, gainers/losers & AI brief |
| `GET` | `/api/v2/stocks/{ticker}` | Consolidated stock quote and fundamentals |
| `POST` | `/api/v2/research` | Comprehensive 7-section equity report (Markdown) |
| `POST` | `/api/v2/research/pdf` | Downloadable equity report (Binary PDF) |
| `GET` | `/api/v2/chat/sessions` | List anonymous client conversation sessions |

---

##  Cloud Deployment

- **Backend (Render Free Tier)**: Uses `Dockerfile` and `render.yaml`. Deploys automatically on `git push origin main` with a built-in health check probe.
- **Keep-Alive Cron**: Automated GitHub Actions workflow (`.github/workflows/demo_keepalive.yml`) prevents Render 15-minute idle spindown during demo periods.
- **Frontend (Vercel)**: Configured via `frontend/vercel.json` for single-page routing and asset caching.
