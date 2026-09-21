# MarketMind-API: Modernization & Full-Stack Transformation Checklist

This checklist tracks the end-to-end transformation of **MarketMind-API** from a legacy, cost-heavy prototype into a modern, production-grade, 100% free-to-host full-stack financial intelligence application powered by **Google Gemini** and modern open-source tooling.

---

## Progress Overview

- [x] **Phase 1**: Codebase Pruning & Clean Architecture Setup
- [ ] **Phase 2**: Free-Tier Provider Integrations & Adapters
- [ ] **Phase 3**: Core RAG & Business Logic Re-Engineering
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
  - [x] Create `.env.example` template.
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

- [ ] **2.1 Google Gemini AI Engine Adapter (`app/infrastructure/llm/`)**
  - [ ] Implement async Gemini client using the latest Google GenAI SDK (`google-genai`).
  - [ ] Implement streaming token generator with Gemini 2.0 / 1.5 Flash.
  - [ ] Implement structured JSON output parsing using Gemini's native schema enforcement.
  - [ ] Add token usage tracking & latency calculation without external paid loggers.
- [ ] **2.2 Zero-Cost Web Search Adapter (`app/infrastructure/search/`)**
  - [ ] Create abstract `SearchEngine` interface (Strategy pattern).
  - [ ] Implement `DuckDuckGoSearcher` using `duckduckgo-search` (`ddgs`) with news and web search modes (100% free, no API key).
  - [ ] Implement optional fallback adapter for `TavilySearcher` / `BraveSearcher` using free monthly tiers.
- [ ] **2.3 Free Financial Market Data Adapter (`app/infrastructure/market/`)**
  - [ ] Replace CMOTS and Playwright scrapers with a unified `YFinanceClient`.
  - [ ] Implement ticker resolution from company names.
  - [ ] Implement real-time price & volume quotes.
  - [ ] Implement fundamental data fetchers (P&L, balance sheets, cash flow statements, key valuation ratios).
- [ ] **2.4 Embedded / In-Process Vector Store (`app/infrastructure/vector_store/`)**
  - [ ] Create abstract `VectorStore` interface.
  - [ ] Implement lightweight in-process vector store using **LanceDB** or local persistent **Chroma** (eliminating Pinecone & remote Chroma server).
  - [ ] Use Gemini `text-embedding-004` or fast local ONNX embeddings (`fastembed`).
- [ ] **2.5 Unified Database Layer (`app/core/database.py`)**
  - [ ] Consolidate database access into modern **Async SQLAlchemy 2.0**.
  - [ ] Configure connection pooling optimized for serverless PostgreSQL (**Neon.tech** or **Supabase**).
  - [ ] Create declarative models for Chat Sessions, Message History, and Dashboard Cache.
  - [ ] Set up Alembic for automated schema migrations.

---

## Phase 3: Core RAG & Business Logic Re-Engineering

Goal: Rebuild the core RAG pipelines to be lean, lightning-fast, and memory-efficient (<512MB RAM).

- [ ] **3.1 High-Performance Streaming Web RAG Service**
  - [ ] Implement async query analyzer (financial intent validation, sub-query generation, ticker detection).
  - [ ] Implement concurrent async HTML scraping using `httpx` + `trafilatura` (with strict timeouts & domain blacklists).
  - [ ] Implement lightweight passage reranking (BM25 or fast cross-encoder) to extract top context.
  - [ ] Construct cohesive, structured financial prompts with strict citation rules.
  - [ ] Stream synthesized answers with citation metadata.
- [ ] **3.2 Gemini Native Multimodal Document RAG Service**
  - [ ] Implement direct PDF ingestion exploiting Gemini's native 1M+ token context window.
  - [ ] Eliminate complex multi-stage PDF deconstruction, table splitting, and OCR pipelines.
  - [ ] Enable native document visual understanding (Gemini natively analyzes financial charts, balance sheet tables, and diagrams in PDFs).
- [ ] **3.3 Community Sentiment & Reddit RAG Service**
  - [ ] Implement Reddit discussion discovery via DuckDuckGo site-specific search.
  - [ ] Extract discussion threads and user comment trees.
  - [ ] Synthesize retail community sentiment and debate summaries.
- [ ] **3.4 Market Dashboard Service with Stale-While-Revalidate**
  - [ ] Replace 24/7 background scheduler with on-demand caching with TTL (Stale-While-Revalidate in Postgres).
  - [ ] Aggregate top market indices (Nifty 50, Sensex, S&P 500, Nasdaq), standout gainers, and losers via `yfinance`.
  - [ ] Generate structured daily market briefs using Gemini Flash.
- [ ] **3.5 Deep Research Pipeline**
  - [ ] Implement automated equity research orchestrator (Executive Summary, Fundamentals, Technicals, Risks, Catalysts).
  - [ ] Generate clean Markdown reports with option to export to downloadable PDF.

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
