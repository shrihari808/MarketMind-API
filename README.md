# MarketMind API (v2)

[![FastAPI](https://img.shields.io/badge/FastAPI-v0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-2.0_Flash-4285F4.svg?logo=google&logoColor=white)](https://ai.google.dev/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.x-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**MarketMind API** is an institutional-grade, full-stack financial intelligence application and API engine. Re-engineered from the ground up for strict **512 MB RAM footprint** and **$0 free-tier cloud deployment** (Render + Vercel + Neon/Supabase), MarketMind combines real-time equity market data, streaming Web RAG, native multimodal document analysis, keyless retail sentiment discovery, and downloadable institutional equity research reports.

---

## 🏛️ Repository Organization

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
├── v1/                   # 🗄️ Legacy Version 1 Archive (Prototypes, legacy files & original docs)
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
└── dev_checklist.md      # Detailed v2 modernization transformation checklist
```

---

## ✨ Features (v2)

- **Streaming Web RAG with Typed SSE**: Real-time multi-angle financial retrieval with concurrent scraping, lightweight BM25 reranking, and citation tracking (`status`, `sources`, `token`, `complete`).
- **Native Multimodal Document RAG**: Direct PDF ingestion leveraging Gemini's native 1M+ token context window—no heavy OCR, no vectorization bottlenecks, with visual balance sheet & chart analysis.
- **Live Market Dashboard (SWR Cached)**: Real-time benchmark indices (Nifty 50, Sensex, S&P 500, Nasdaq), standout gainers/losers, and AI daily macro briefs with Stale-While-Revalidate caching in PostgreSQL/SQLite.
- **Embedded LanceDB Semantic News Cache & Document Vault**: High-speed Apache Arrow columnar vector store running completely in-process (<30 MB RAM overhead).
- **Keyless Retail Community Sentiment**: Reddit discussion extraction via JSON endpoints without requiring paid Reddit API credentials.
- **Deep Equity Research & In-Memory PDF Export**: Automated 7-section institutional research generator producing downloadable PDF reports via ReportLab.
- **Sliding-Window IP Rate Limiter**: 25 req/min protection with dynamic runtime inspection endpoints (`/api/v2/health/rate-limit`).
- **Anonymous Device Sessions**: Multi-turn conversation persistence isolated by browser client UUID (`X-Client-ID`).

---

## 🚀 Quick Start

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

## 🧪 Testing

Run the automated test suite using `pytest`:

```bash
pytest
```

---

## 📡 API Endpoints (v2)

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

## 📦 Cloud Deployment

- **Backend (Render Free Tier)**: Uses `Dockerfile` and `render.yaml`. Deploys automatically on `git push origin main` with a built-in health check probe.
- **Keep-Alive Cron**: Automated GitHub Actions workflow (`.github/workflows/demo_keepalive.yml`) prevents Render 15-minute idle spindown during demo periods.
- **Frontend (Vercel)**: Configured via `frontend/vercel.json` for single-page routing and asset caching.
