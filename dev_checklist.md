# MarketMind-API: Modernization & Full-Stack Transformation Checklist

This checklist tracks the end-to-end transformation of **MarketMind-API** from a legacy, cost-heavy prototype into a modern, production-grade, 100% free-to-host full-stack financial intelligence application powered by **Google Gemini** and modern open-source tooling.

---

## Progress Overview

- [x] **Phase 1**: Codebase Pruning & Clean Architecture Setup
- [x] **Phase 2**: Free-Tier Provider Integrations & Adapters
- [x] **Phase 3**: Core RAG & Business Logic Re-Engineering
- [ ] **Phase 4**: API Modernization & Standardized SSE Streaming
- [ ] **Phase 5**: Modern Full-Stack Frontend (Web UI)
- [ ] **Phase 6**: Testing, Dockerization & $0 Cloud Deployment

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
  - [x] Implement async query analyzer (`QueryAnalyzer`): financial intent validation, multi-angle sub-query generation (recency, analytical, factual), ticker detection, and conversational follow-up resolution.
  - [x] Implement concurrent async HTML scraping using `httpx` + `trafilatura` (with strict timeouts & 5MB memory guard).
  - [x] Implement lightweight pure-Python BM25 passage reranking (`BM25Reranker`) with publisher domain diversification (max 2 per domain) and optional zero-PyTorch Gemini API hybrid reranking (`HybridReranker`).
  - [x] Inject real-time market quotes directly into prompt context when tickers are detected.
  - [x] Stream synthesized answers with strict citation metadata (`[1]`, `[2]`).
- [x] **3.2 Gemini Native Multimodal Document RAG Service (`DocumentRAGService`)**
  - [x] Implement direct PDF ingestion exploiting Gemini's native 1M+ token context window.
  - [x] Eliminate complex multi-stage PDF deconstruction, table splitting, and OCR pipelines.
  - [x] Enable native document visual understanding (Gemini natively analyzes financial charts, balance sheet tables, and diagrams in PDFs).
- [x] **3.3 Community Sentiment & Reddit RAG Service (`RedditRAGService`)**
  - [x] Implement Reddit discussion discovery via search engine site queries without requiring paid Reddit API keys.
  - [x] Extract discussion threads and user comment trees via Reddit JSON endpoint with Trafilatura fallback.
  - [x] Synthesize retail community sentiment and debate summaries (Bullish vs. Bearish consensus, normalized score, argument breakdown).
- [x] **3.4 Market Dashboard Service with Stale-While-Revalidate (`MarketDashboardService`)**
  - [x] Replace 24/7 background scheduler with on-demand caching with TTL (Stale-While-Revalidate in Postgres/SQLite).
  - [x] Provide configurable active/inactive toggle (`DASHBOARD_ENABLED`) and configurable cache TTL in hours (`DASHBOARD_CACHE_TTL_HOURS`).
  - [x] Aggregate top market indices (Nifty 50, Sensex, S&P 500, Nasdaq), standout gainers, and losers via `yfinance`.
  - [x] Generate structured daily market briefs using Gemini Flash.
- [x] **3.5 Deep Research Pipeline (`DeepResearchService`)**
  - [x] Implement automated equity research orchestrator (Executive Summary, Business Profile, Fundamentals, Industry Moat, Risks, Catalysts, Valuation & Recommendation).
  - [x] Generate clean Markdown reports with option to export to publication-ready downloadable PDF in-memory via `ReportLab`.

---

## 4. Phase 4: API Modernization & Standardized SSE Streaming

Goal: Replace ad-hoc string formatting with industry-standard protocols, clean REST routes, and robust error handling.

- [ ] **4.1 Standardized Server-Sent Events (SSE) Protocol**
  - [ ] Replace plain-text magic-string streams (`& Generating search plan...`) with typed SSE events (`text/event-stream`):
    - `event: status` -> Progress step updates for UI indicators.
    - `event: sources` -> Cited article metadata (title, URL, publisher).
    - `event: token` -> Incremental response text chunks.
    - `event: error` -> Structured error messages.
    - `event: complete` -> Total token usage and generation latency.
- [ ] **4.2 RESTful Endpoint Cleanup**
  - [ ] `/api/v1/rag/web`: POST streaming web RAG endpoint.
  - [ ] `/api/v1/rag/document`: POST multipart PDF upload & chat query.
  - [ ] `/api/v1/rag/reddit`: POST community sentiment analysis.
  - [ ] `/api/v1/dashboard`: GET live market indices & trending stocks.
  - [ ] `/api/v1/stocks/{ticker}`: GET detailed fundamentals & quotes.
  - [ ] `/api/v1/research`: POST deep equity report generator.
- [ ] **4.3 Security & Middleware**
  - [ ] Standardize API key authorization dependency (`X-API-Key`) with clear 401/403 status codes.
  - [ ] Configure strict CORS middleware for frontend production and preview domains.
  - [ ] Add global exception handlers and request logging middleware.

---

## Phase 5: Modern Full-Stack Frontend (Web UI)

Goal: Build a responsive, dark-mode financial terminal web application connecting to the modernized backend.

- [ ] **5.1 Project Setup & Design System**
  - [ ] Initialize Next.js 15 (App Router) or Vite + React 19 project.
  - [ ] Configure Tailwind CSS and install **shadcn/ui** components (Button, Input, Card, Badge, Dialog, Tabs, Table).
  - [ ] Implement financial dark-mode theme with sleek typography.
- [ ] **5.2 Market Overview Dashboard**
  - [ ] Live ticker marquee for major indices.
  - [ ] Standout market gainers & losers cards with price change indicators.
  - [ ] Interactive price chart using **TradingView Lightweight Charts** or **Recharts**.
- [ ] **5.3 Streaming AI Financial Search & Chat**
  - [ ] Omnibar search input with query suggestion pills.
  - [ ] Live streaming message bubble consuming backend SSE stream.
  - [ ] Step-by-step progress stepper (e.g. *Searching web* -> *Reading articles* -> *Analyzing financials*).
  - [ ] Interactive source citation cards and badge pills.
- [ ] **5.4 Multimodal Document Analyzer UI**
  - [ ] Drag-and-drop PDF upload component.
  - [ ] Split-view layout: PDF preview on left, Gemini Q&A conversation on right.
  - [ ] Quick-action prompts (e.g., *Analyze balance sheet*, *Identify major risk factors*, *Extract EBITDA growth*).
- [ ] **5.5 Deep Research Report Viewer**
  - [ ] Markdown-rendered equity research report view.
  - [ ] Download as PDF button.

---

## Phase 6: Testing, Dockerization & $0 Cloud Deployment

Goal: Deploy both frontend and backend to production on 100% free tiers with automated continuous deployment.

- [ ] **6.1 Automated Testing**
  - [ ] Unit tests for all adapters (Searcher, MarketData, VectorStore) with mocked external calls.
  - [ ] Integration tests for RAG pipeline flows and SSE generators.
  - [ ] API endpoint contract tests using FastAPI `TestClient`.
- [ ] **6.2 Production Dockerfile**
  - [ ] Multi-stage, non-root Docker build for FastAPI backend.
  - [ ] Ultra-lean image size (<300 MB) with zero browser/PyTorch bloat.
  - [ ] Verify startup memory footprint stays well under 512MB RAM limit.
- [ ] **6.3 Cloud Database Setup (Free)**
  - [ ] Provision serverless PostgreSQL on **Neon.tech** or **Supabase** (free tier).
  - [ ] Run initial Alembic migrations to create tables.
- [ ] **6.4 Backend Deployment (Free)**
  - [ ] Connect GitHub repository to **Render.com** or **Koyeb** (Free Web Service).
  - [ ] Configure environment variables (`GEMINI_API_KEY`, `DATABASE_URL`, `ALLOWED_ORIGINS`).
  - [ ] Verify health-check endpoint (`/health`).
- [ ] **6.5 Frontend Deployment (Free)**
  - [ ] Deploy Next.js / React app to **Vercel** (free tier).
  - [ ] Configure backend API base URL environment variable.
  - [ ] Test end-to-end streaming RAG, document analysis, and dashboard live on custom/vercel.app domain.
