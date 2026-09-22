# MarketMind-API: Modernization & Full-Stack Transformation Checklist

This checklist tracks the end-to-end transformation of **MarketMind-API** from a legacy, cost-heavy prototype into a modern, production-grade, 100% free-to-host full-stack financial intelligence application powered by **Google Gemini** and modern open-source tooling.

---

## Progress Overview

- [x] **Phase 1**: Codebase Pruning & Clean Architecture Setup
- [x] **Phase 2**: Free-Tier Provider Integrations & Adapters
- [x] **Phase 3**: Core RAG & Business Logic Re-Engineering
- [x] **Phase 4**: API Modernization & Standardized SSE Streaming (MarketMind API v2)
- [x] **Phase 5**: Modern Full-Stack Frontend (MarketMind v2 Web Terminal)
- [x] **Phase 6**: Testing, Dockerization & $0 Cloud Deployment

---

## Phase 1: Codebase Pruning & Clean Architecture Setup

Goal: Eliminate technical debt, legacy files, hardcoded developer paths, import side-effects, and bloated dependencies before writing new code.

- [x] **1.1 Junk Code & Legacy File Removal**
  - [x] Delete dead / deprecated files (`api/fundamentals_rag/fundamental_chat.py`, `api/graph_openai1.py`).
  - [x] Remove scratch notes and obsolete curl dumps (`windows curls.txt`, `localhost curls.txt`).
  - [x] Remove generated artifacts checked into version control (`api/deep_research/Tata_Motors_Stock_Analysis.pdf`, `db_tester.py`, `import_graph.py`).
  - [x] Add `data/` and `outputs/` to `.gitignore`.
- [x] **1.2 Dependency Sanitization**
  - [x] Replace bloated 224-package frozen `requirements.txt` with a lean, categorized requirement set.
  - [x] Remove heavy, unnecessary dependencies (PyTorch, Transformers, Playwright, pytube, Streamlit).
  - [x] Add modern, lightweight packages: `google-genai`, `yfinance`, `duckduckgo-search`, `pydantic-settings`, `httpx`, `fastapi`.
- [x] **1.3 Type-Safe Configuration Layer (`app/core/config.py`)**
  - [x] Create Pydantic v2 `BaseSettings` schema reading from `.env`.
  - [x] **Eliminate all import-time side-effects** (no eager Pinecone/Chroma network calls or model downloads upon importing settings).
  - [x] Configure environment variables for `GEMINI_API_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `ENVIRONMENT`.
  - [x] Add developer search configuration: `SEARCH_PROVIDER` (`duckduckgo` | `serper` | `brave`), `SERPER_API_KEY`, `BRAVE_API_KEY`.
  - [x] Create and update `.env.example` template with optional search API keys.
- [x] **1.4 Clean Architecture Directory Structure & Domain Layer**
  - [x] Scaffold standard clean-architecture folders:
    - `app/core/` (settings, logging, security)
    - `app/domain/` (schemas: `rag.py`, `market.py`; interfaces: `search.py`, `scraper.py`, `market.py`, `llm.py`, `vector_store.py`)
    - `app/infrastructure/` (search, scrapers, financial data, vector store adapters)
    - `app/services/` (RAG pipelines, research generator, dashboard services)
    - `app/api/` (FastAPI route handlers, SSE formatters)


---

## Phase 2: Free-Tier Provider Integrations & Adapters

Goal: Implement decoupled, pluggable adapters for LLMs, search, market data, vector storage, and relational persistence that operate completely within $0 free tiers.

- [x] **2.1 Google Gemini AI Engine Adapter (`app/infrastructure/llm/gemini.py`)**
  - [x] Implement async Gemini client using Google GenAI SDK.
  - [x] Implement streaming token generator with Gemini 2.0 / 1.5 Flash.
  - [x] Implement structured JSON output parsing using native schema enforcement.
  - [x] Support native multimodal PDF/document streaming without OCR/chunking.
  - [x] Safe import with clear warning if `GEMINI_API_KEY` is not yet set.
- [x] **2.2 Configurable Multi-Search Architecture & Optional APIs (`app/infrastructure/search/`)**
  - [x] Implement `SearchEngineFactory` with developer-configurable provider (`SEARCH_PROVIDER="duckduckgo" | "serper" | "brave"`).
  - [x] **DuckDuckGo (Default & Free)**: Upgraded to `ddgs>=9.16.0` (100% free, zero key needed, automatic worldwide fallback when regional queries return empty).
  - [x] **Serper.dev (Optional Paid/Freemium API)**: Added `SerperSearcher` for Google web & financial news search via Serper API; parses relative dates ("2 hours ago", "3 days ago") and absolute dates into ISO format; graceful degradation if key is omitted.
  - [x] **Brave Search (Optional API)**: Added `BraveSearcher` for web and financial news search via Brave Search API; normalizes timestamps and handles news-to-web fallback.
  - [x] Standardize all search providers into uniform domain `SourceCitation` schemas.
- [x] **2.3 Free Financial Market Data Adapter (`app/infrastructure/market/yfinance_client.py`)**
  - [x] Implement `YFinanceMarketClient` (adhering to `MarketDataClient`).
  - [x] Ticker resolution for Indian (.NS) and US exchanges.
  - [x] Real-time prices, market indices (Nifty, Sensex, S&P 500, Nasdaq), and top gainers/losers.
  - [x] Complete company fundamentals (P/E ratio, market cap, balance sheets, cash flow).
- [x] **2.4 Embedded / In-Process Vector Store (`app/infrastructure/vector_store/lance_store.py`)**
  - [x] Implement `LanceVectorStore` (adhering to `VectorStore`).
  - [x] In-process Apache Arrow columnar storage (<30 MB RAM footprint, zero separate server).
  - [x] Fast text chunker, vector similarity search, and collection management.
- [x] **2.5 Async Web Scraper with Dynamic Redirects & Table Extraction (`app/infrastructure/scrapers/web_scraper.py`)**
  - [x] Implement `TrafilaturaWebScraper` (adhering to `WebScraper`).
  - [x] **Memory Constraint Evaluation**: Analyzed IBM `docling` and intentionally avoided it for cloud deployment due to ~2GB PyTorch neural model footprint causing OOM kill on 512MB free tiers.
  - [x] **Dynamic Redirect Handling**: Async HTTP requests via `httpx` with `follow_redirects=True`, `max_redirects=5`, and automatic final canonical URL tracking.
  - [x] **512MB RAM Safeguard**: Enforces a strict 5MB payload limit to prevent runaway memory usage.
  - [x] **Lightweight HTML Table Extraction**: Built an embedded `BeautifulSoup` table-to-markdown parser (<1MB RAM overhead, 0% crash risk) converting HTML tables into clean GitHub Markdown (`| Col 1 | Col 2 |`) appended to article text.
  - [x] Non-blocking CPU extraction via `trafilatura` run in thread pool.
- [x] **2.6 Unified Database Layer (`app/core/database.py`)**
  - [x] Consolidate database access into modern **Async SQLAlchemy 2.0**.
  - [x] Support serverless PostgreSQL (Neon.tech / Supabase) via `asyncpg`.
  - [x] Support automatic local SQLite fallback (`sqlite+aiosqlite`) for offline zero-config dev.
  - [x] Create declarative models for `ChatMessageRecord` and `DashboardCacheRecord`.

---

## Phase 3: Core RAG & Business Logic Re-Engineering
 
Goal: Rebuild the core RAG pipelines to be lean, lightning-fast, and memory-efficient (<512MB RAM).

- [x] **3.1 High-Performance Streaming Web RAG Service (`WebRAGService`)**
  - [x] Implement async query analyzer (`QueryAnalyzer`): financial intent validation with expanded 162-term financial taxonomy, multi-angle sub-query generation (recency, analytical, factual), ticker detection, and conversational follow-up resolution.
  - [x] Implement concurrent async HTML scraping using `httpx` + `trafilatura` (with strict timeouts & 5MB memory guard).
  - [x] Implement lightweight pure-Python BM25 passage reranking (`BM25Reranker`) with publisher domain diversification (max 2 per domain) and optional zero-PyTorch Gemini API hybrid reranking (`HybridReranker`).
  - [x] Support configurable passage chunking (`RAG_CHUNK_SIZE=400`, `RAG_CHUNK_OVERLAP=50`), search limits (`MAX_SEARCH_RESULTS=7`), and generation temperature (`LLM_TEMPERATURE=0.2`).
  - [x] Inject real-time market quotes directly into prompt context when tickers are detected.
  - [x] Stream synthesized answers with strict citation metadata (`[1]`, `[2]`).
- [x] **3.2 Gemini Native Multimodal Document RAG Service (`DocumentRAGService`)**
  - [x] Implement direct PDF ingestion exploiting Gemini's native 1M+ token context window.
  - [x] Eliminate complex multi-stage PDF deconstruction, table splitting, and OCR pipelines.
  - [x] Enable native document visual understanding (Gemini natively analyzes financial charts, balance sheet tables, and diagrams in PDFs).
- [x] **3.3 Community Sentiment & Reddit RAG Service (`RedditRAGService`)**
  - [x] Implement Reddit discussion discovery via search engine site queries without requiring paid Reddit API keys.
  - [x] Extract discussion threads and user comment trees via Reddit JSON endpoint with Trafilatura fallback.
  - [x] Synthesize retail community sentiment and debate summaries (Bullish vs. Bearish consensus, normalized score, argument breakdown) with configurable temperature and search limits.
- [x] **3.4 Market Dashboard Service with Stale-While-Revalidate (`MarketDashboardService`)**
  - [x] Replace 24/7 background scheduler with on-demand caching with TTL (Stale-While-Revalidate in Postgres/SQLite).
  - [x] Provide configurable active/inactive toggle (`DASHBOARD_ENABLED`) and configurable cache TTL in hours (`DASHBOARD_CACHE_TTL_HOURS`).
  - [x] Aggregate top market indices (Nifty 50, Sensex, S&P 500, Nasdaq), standout gainers, and losers via `yfinance`.
  - [x] Generate structured daily market briefs using Gemini Flash with configurable temperature.
- [x] **3.5 Deep Research Pipeline (`DeepResearchService`)**
  - [x] Implement automated equity research orchestrator (Executive Summary, Business Profile, Fundamentals, Industry Moat, Risks, Catalysts, Valuation & Recommendation).
  - [x] Support dual generation strategies: cohesive single-pass vs. granular section-by-section multi-prompting via `RESEARCH_SECTION_BY_SECTION`.
  - [x] Generate clean Markdown reports with option to export to publication-ready downloadable PDF in-memory via `ReportLab`.
- [x] **3.6 Service-Wide Observability & Embedding Batching**
  - [x] Add rich, structured logging (`logger.info`, `logger.debug`, `logger.warning`) across all services.
  - [x] Configurable batch size for embedding generation (`EMBEDDING_BATCH_SIZE=32`) to prevent API throttling and payload size overflows.

---

## 4. Phase 4: API Modernization & Standardized SSE Streaming (MarketMind API v2)

Goal: Replace legacy ad-hoc routes with MarketMind v2 REST endpoints, standardized Server-Sent Events (SSE) streaming protocols, anonymous client UUID chat isolation, and IP-wise rate limiting (25 req/min).

- [x] **4.1 Standardized Server-Sent Events (SSE) Protocol**
  - [x] Replaced plain-text magic-string streams with typed SSE events (`text/event-stream`):
    - `event: status` -> Progress step updates for UI indicators.
    - `event: sources` -> Cited article metadata (title, URL, publisher).
    - `event: token` -> Incremental response text chunks.
    - `event: error` -> Structured error messages.
    - `event: complete` -> Total token usage and generation latency.
- [x] **4.2 RESTful v2 Endpoint Architecture (`/api/v2/`)**
  - [x] `/api/v2/rag/web`: POST streaming web RAG endpoint with SSE support and automatic conversation turn persistence.
  - [x] `/api/v2/rag/document`: POST multipart PDF upload & chat query with native multimodal SSE streaming.
  - [x] `/api/v2/rag/document/summary`: POST multipart PDF upload for executive financial summary.
  - [x] `/api/v2/rag/reddit`: POST community sentiment analysis without paid Reddit keys.
  - [x] `/api/v2/dashboard`: GET live market indices, trending gainers/losers, and AI macro brief (SWR cached).
  - [x] `/api/v2/stocks/{ticker}`: GET consolidated real-time quote + fundamentals.
  - [x] `/api/v2/stocks/{ticker}/quote`: GET real-time stock quote.
  - [x] `/api/v2/stocks/{ticker}/fundamentals`: GET financial fundamentals and valuation ratios.
  - [x] `/api/v2/research`: POST deep 7-section equity report generator (JSON markdown).
  - [x] `/api/v2/research/pdf`: POST deep equity report downloadable PDF compiled in-memory via ReportLab.
  - [x] `/api/v2/health`: GET system health, active providers, and database connectivity.
- [x] **4.3 Anonymous Client UUID & Chat History (`/api/v2/chat/`)**
  - [x] Implemented zero-login device identification via browser client UUID (`X-Client-ID`).
  - [x] Isolated multi-turn chat conversations and session history per `client_id` in `ChatMessageRecord`.
  - [x] `/api/v2/chat/sessions`: GET all conversations for the client.
  - [x] `/api/v2/chat/sessions/{session_id}`: GET full message history for a conversation.
  - [x] `/api/v2/chat/sessions/{session_id}`: DELETE a conversation.
- [x] **4.4 Security, Rate Limiting & Middleware**
  - [x] In-memory sliding-window IP rate limiter enforcing **requests per minute per IP** (default: 25 req/min) with proxy header resolution (`X-Forwarded-For`).
  - [x] Configurable active toggle (`RATE_LIMIT_ENABLED`) and threshold (`RATE_LIMIT_PER_MINUTE`) via `.env` and `app/core/config.py`.
  - [x] Runtime inspection and dynamic control endpoints: `GET /api/v2/health/rate-limit` and `POST /api/v2/health/rate-limit` (toggle on/off, adjust threshold, reset history without restart).
  - [x] Returns HTTP 429 Too Many Requests with `Retry-After` header when limit is exceeded.
  - [x] Standardize API key authorization dependency (`X-API-Key`) with clear 401/403 status codes.
  - [x] Configured CORS middleware for production and preview domains.
  - [x] Process timing middleware (`X-Process-Time`) and global exception handler.
  - [x] Lifespan database initialization and connection pool cleanup.
  - [x] Root `main.py` entrypoint updated to delegate to `app.main:app`.

---

## Phase 5: Modern Full-Stack Frontend (MarketMind v2 Web Terminal)

Goal: Build a responsive, dark-mode financial terminal web application connecting to the modernized backend.

- [x] **5.1 Project Setup, Design System & Raleway Typography**
  - [x] Initialized modern Vite + React 19 + TypeScript + Tailwind CSS application (`frontend/`).
  - [x] Configured Google Font **Raleway** (`weights: 100..900`) throughout the entire terminal application.
  - [x] Implemented institutional financial dark-mode theme (`#080C14` background, elevated `#0E1626` panels, `#10B981` bullish green, `#F43F5E` bearish red).
- [x] **5.2 Persistent Sidebar & Navigation**
  - [x] Always-visible persistent sidebar with MarketMind v2 branding and system tier badges.
  - [x] New Chat action button and isolated chat sessions history drawer.
  - [x] Quick navigation tabs across all institutional terminal features.
- [x] **5.3 Market Overview Dashboard & Live Marquee**
  - [x] Top live continuous ticker marquee for benchmark indices and blue-chip stocks.
  - [x] Landing page default state showcasing live benchmark indices (Nifty 50, Sensex, S&P 500, Nasdaq).
  - [x] Standout market gainers & decliners cards with price change indicators.
  - [x] Daily Gemini Flash AI Macro Brief.
- [x] **5.4 Streaming AI Financial Search & Dynamic Omnibar**
  - [x] Docked bottom Omnibar with country selector dropdown (🇮🇳 India / 🇺🇸 United States).
  - [x] Dynamic transition: typing prompt or clicking shortcut transitions landing dashboard to live streaming chat.
  - [x] Dynamic top-left **"Market Dashboard"** button with icon to return to dashboard anytime.
  - [x] Real-time typed SSE streaming consumer (`status`, `sources`, `token`, `complete`, `error`).
  - [x] Progress stepper pills and interactive source citation cards.
- [x] **5.5 Multimodal Document Analyzer UI**
  - [x] Drag-and-drop PDF upload component with file size guard.
  - [x] Split-view layout: In-browser PDF preview on left, Gemini multimodal Q&A on right.
  - [x] Quick-action prompts (Executive Summary, Balance Sheet Moat, Major Risks).
- [x] **5.6 Deep Research Report Viewer & PDF Download**
  - [x] Institutional 7-section report viewer with markdown styling.
  - [x] One-click "Download PDF" triggering backend in-memory ReportLab stream into browser download.
- [x] **5.7 Reddit Community Sentiment & Stock Inspector**
  - [x] Keyless retail community sentiment gauge with Bullish/Bearish thesis breakdown.
  - [x] Real-time stock quote and financial fundamentals inspector (P/E, P/B, ROE, Debt/Equity).
- [x] **5.8 Hybrid Deployment & Full-Stack Integration**
  - [x] FastAPI optionally mounts `frontend/dist` static assets and serves `index.html` on root with `Accept: text/html` while preserving JSON API negotiation for programmatic clients.


---

## Phase 6: Testing, Dockerization & $0 Cloud Deployment

Goal: Deploy both frontend and backend to production on 100% free tiers with automated continuous deployment.

- [x] **6.1 Unified Automated Testing Suite**
  - [x] Service-level integration test suite (`scratch/test_phase3_services.py`): BM25 reranker, financial query analyzer, Web RAG, document RAG, Reddit sentiment, dashboard SWR, deep research.
  - [x] API v2 endpoint integration test suite (`scratch/test_phase4_api_v2.py`): rate-limiting toggle, client UUID isolation, SSE streaming, document Q&A, stock quotes, ReportLab PDF download.
  - [x] Full-stack web terminal integration test suite (`scratch/test_phase5_fullstack.py`): HTML negotiation, static assets, Raleway font.
  - [x] Master cloud readiness regression suite (`scratch/test_phase6_suite.py`): 100% pass across all 4 architectural layers.
- [x] **6.2 Production Multi-Stage Dockerfile (`Dockerfile` & `.dockerignore`)**
  - [x] Multi-stage build: Stage 1 compiles Vite + React 19 frontend into `frontend/dist`; Stage 2 packages Python 3.11-slim backend runtime.
  - [x] Strict 512 MB RAM safeguards: `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OMP_NUM_THREADS=1`.
  - [x] Non-root security user `appuser` (UID 1000).
  - [x] Ultra-lean image size (<300 MB) with zero PyTorch bloat and built-in Docker healthcheck on `/api/v2/health`.
- [x] **6.3 Infrastructure-as-Code Configuration (`render.yaml` & `frontend/vercel.json`)**
  - [x] Created `render.yaml` Blueprint for 1-click Render Web Service deployment with automatic continuous deployment on `git push origin main`.
  - [x] Configured all environment variables (`RATE_LIMIT_PER_MINUTE`, `SEARCH_PROVIDER`, `GEMINI_MODEL`, `DASHBOARD_ENABLED`, etc.) with sync prompts for secrets.
  - [x] Created `frontend/vercel.json` configuring SPA route rewrites (`/* -> /index.html`) and asset cache headers.
- [x] **6.4 Zero-Cost Cloud Database Guide (Neon / Supabase)**
  - [x] Documented serverless PostgreSQL connection string setup (`postgresql+asyncpg://...`) with local SQLite dev fallback.
- [x] **6.5 Frontend & Backend Cloud Hosting Playbook**
  - [x] Documented step-by-step connection for Render.com (Backend Docker) and Vercel (Frontend SPA).
  - [x] Documented runtime inspection endpoints (`/api/v2/health/rate-limit`) and dashboard environment variable management for zero-restart trial and error.

