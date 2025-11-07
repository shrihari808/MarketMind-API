# Developer Guide

This guide provides an overview of the codebase structure and explains how each endpoint works.

## Project Structure

```
app_service/
├── main.py                 # FastAPI app initialization, lifespan management, CORS setup
├── config.py               # Configuration, environment variables, LLM/embedding initialization
├── api/
│   ├── router.py          # Master router that includes all endpoint routers
│   ├── security.py        # API key authentication
│   ├── dashboard/         # Dashboard-related endpoints
│   │   ├── dashboard.py   # Main dashboard endpoint
│   │   ├── portfolio/    # Portfolio analysis
│   │   ├── stock/        # Stock snapshot
│   │   └── trending.py    # Trending stocks
│   ├── doc_rag/          # Document RAG endpoints
│   │   └── doc_chat.py   # Document chat with PDF support
│   └── deep_research/    # Deep research pipeline
│       └── views.py      # Research endpoint views
├── streaming/
│   └── streaming.py     # Streaming RAG endpoints (web, reddit, youtube, cmots)
└── ecosystem.config.js   # PM2 process configuration
```

## Endpoint Documentation

### Dashboard Endpoints

#### `GET /dashboard`
**Location:** `api/dashboard/dashboard.py`

Generates market dashboard snapshot for a specific country.

**How it works:**
1. Checks for cached dashboard data (15-minute freshness)
2. If cache miss, triggers on-demand generation:
   - Aggregates market data using `aggregate_and_process_data()`
   - Processes trending stocks
   - Generates market insights
3. Streams progress updates to client
4. Returns JSON dashboard data

**Parameters:**
- `country`: Country code (e.g., "IN", "US")

**Key Functions:**
- `aggregate_and_process_data()`: Main aggregation function (scheduled hourly)

---

#### `GET /dashboard/portfolio`
**Location:** `api/dashboard/portfolio/portfolio_snapshot.py`

Generates portfolio-specific dashboard with news and analysis.

**How it works:**
1. Fetches latest news for portfolio stocks using Serper API
2. Scrapes article content from URLs
3. Creates vector store and indexes content
4. Uses scoring service to rank and extract relevant context
5. Generates LLM-powered insights for portfolio
6. Streams progress with visual progress bar
7. Returns comprehensive portfolio analysis

**Parameters:**
- `portfolio`: List of stock tickers (query parameter)

**Key Components:**
- `SerperDashboard`: News fetching service
- `DashboardVectorStore`: Vector storage for news content
- `DashboardScoringService`: Content ranking and scoring
- `PortfolioLLMGenerator`: LLM-based insight generation

---

#### `GET /stock`
**Location:** `api/dashboard/stock/stock_snapshot.py`

Generates snapshot dashboard for a single stock.

**How it works:**
Similar to portfolio endpoint but focused on a single stock:
1. Fetches news for the stock
2. Scrapes and indexes content
3. Generates stock-specific insights
4. Returns analysis with latest news and key issues

**Parameters:**
- `stock_name`: Stock ticker or name

---

#### `GET /dashboard/trending`
**Location:** `api/dashboard/trending.py`

Retrieves trending stocks for a country.

**How it works:**
1. Checks for cached trending data (1-hour freshness)
2. If cache miss, scrapes trending stocks using Serper API
3. Returns list of trending stocks with metadata

**Parameters:**
- `country`: Country code (default: "IN")

---

### Streaming RAG Endpoints

#### `POST /web_rag`
**Location:** `streaming/streaming.py`

Advanced web-based RAG with multi-tier search and reranking.

**How it works:**
1. **Preprocessing**: Validates query and generates sub-queries (recency, analytical, factual)
2. **Tier 1 - Recency Search**: Searches for latest news (past day) using Serper API
3. **Tier 2 - Analytical & Factual**: Parallel searches for analysis and background info
4. **Scraping**: Concurrently scrapes article content from URLs
5. **Reranking**: Uses scoring service to rank content by relevance
6. **Context Generation**: Creates enhanced context from top passages
7. **Numerical Data**: If query requires stock data, fetches real-time prices
8. **LLM Synthesis**: Streams final answer using context and chat history
9. **Post-processing**: Logs tokens, updates credits, stores history

**Key Features:**
- Multi-tier search strategy
- Source diversification
- Real-time stock data integration
- Streaming response
- Token usage tracking

**Parameters:**
- `query`: User's search query
- `session_id`: Session identifier
- `country`: Country code for search
- `user_id`, `plan_id`, `prompt_history_id`: User tracking

---

#### `POST /reddit_rag`
**Location:** `streaming/streaming.py`

Reddit-based RAG for community discussions and sentiment.

**How it works:**
1. Validates query relevance
2. Searches Reddit using Serper API
3. Scrapes Reddit post content and comments
4. Creates vector store from scraped content
5. Retrieves relevant chunks using semantic search
6. Reranks passages by relevance
7. Generates answer focusing on community sentiment
8. Streams response with source citations

**Key Features:**
- Community sentiment analysis
- Discussion thread processing
- Multiple perspective aggregation

---

#### `POST /yt_rag`
**Location:** `streaming/streaming.py`

YouTube video RAG for financial video content.

**How it works:**
1. Extracts video ID from YouTube URL
2. Fetches video transcript using YouTube API
3. Validates video relevance to finance
4. Chunks transcript content
5. Creates vector store and retrieves relevant segments
6. Generates summary with key points and sentiment
7. Streams response

**Note:** Endpoint implementation details are in `streaming/yt_stream.py`

---

#### `POST /cmots_rag`
**Location:** `streaming/streaming.py`

CMOTS-specific news RAG endpoint.

**How it works:**
- Optimized for CMOTS news data
- Similar pipeline to web_rag but specialized for CMOTS sources

**Note:** Currently a placeholder implementation

---

### Document RAG Endpoints

#### `POST /documentchat`
**Location:** `api/doc_rag/doc_chat.py`

Alternative document chat endpoint with S3 integration.

**How it works:**
1. Downloads document from S3 bucket
2. Parses document (PDF, TXT, DOCX)
3. Validates token count (max 10,000 tokens)
4. Splits document into chunks
5. Creates ChromaDB collection
6. Stores embeddings
7. Answers questions using retrieval-augmented generation
8. Maintains conversation history in PostgreSQL

**Key Functions:**
- `create_doc_embeddings()`: Creates vector store from S3 document
- `documentchat()`: Main chat function with RAG

**Parameters:**
- `file_name`: Collection name (identifier)
- `question`: User's question
- `session_id`: Session identifier

---

#### `POST /add_attachments`
**Location:** `api/doc_rag/doc_chat.py`

Uploads and processes documents from S3.

**How it works:**
1. Downloads file from S3 using object key
2. Parses based on file type (PDF, TXT, DOCX)
3. Validates document size (token limit)
4. Creates ChromaDB collection with embeddings
5. Returns collection name for future queries

**Parameters:**
- `object_key`: S3 object key
- `file_name`: Collection identifier

---

#### `POST /document_suggestions`
**Location:** `api/doc_rag/doc_chat.py`

Generates suggested questions from a document.

**How it works:**
1. Downloads document from S3
2. Splits into large chunks
3. Generates questions for each chunk using HuggingFace model
4. Selects top 20 most important questions
5. Returns list of suggested questions

**Key Functions:**
- `generate_question()`: Generates questions per chunk
- `top20questions()`: Selects best questions

---

### Deep Research Endpoint

#### `POST /deep_research/`
**Location:** `api/deep_research/views.py`

Initiates comprehensive research pipeline in the background.

**How it works:**
1. Accepts research query
2. Determines if it's stock analysis or general research
3. If stock analysis:
   - Uses `StockResearchPipeline` to generate comprehensive PDF report
   - Includes financial analysis, news, trends
4. If general research:
   - Uses `run_deep_research()` for topic-based research
5. Runs in background (non-blocking)
6. Returns immediately with task confirmation

**Parameters:**
- `query`: Research topic or stock name
- `is_stock_analysis`: Boolean flag for stock vs general research

**Key Components:**
- `StockResearchPipeline`: Comprehensive stock analysis
- `run_deep_research()`: General research pipeline

---

## Key Configuration Files

### `main.py`
- FastAPI application initialization
- Database connection pool management
- Scheduled tasks (data aggregation, trending stocks)
- CORS middleware configuration
- Master router inclusion

### `config.py`
- Environment variable loading
- LLM and embedding model initialization
- Vector store setup (Pinecone, ChromaDB)
- API key configuration
- Scoring weights and thresholds

### `api/router.py`
- Master router that includes all endpoint routers
- Organizes endpoints by tags
- Central routing configuration

### `ecosystem.config.js`
- PM2 process configuration
- Defines two processes:
  1. `app_service`: Main FastAPI application
  2. `chroma_db`: ChromaDB server

## Common Patterns

### Authentication
Most endpoints use `api_key_auth` dependency from `api/security.py`:
```python
api_key: str = Depends(api_key_auth)
```

### Database Access
Endpoints access database pool via FastAPI dependency:
```python
db_pool: asyncpg.Pool = Depends(get_db_pool)
```

### Streaming Responses
Many endpoints use `StreamingResponse` for real-time updates:
```python
return StreamingResponse(stream_generator(), media_type="text/plain")
```

### Token Usage Tracking
Endpoints track LLM token usage using:
```python
from token_logger import log_token_usage
```

### Vector Stores
Multiple vector store implementations:
- Pinecone (primary for news/content)
- ChromaDB (for documents, local storage)
- Session-based in-memory stores

## Scheduled Tasks

Configured in `main.py` lifespan:
- `aggregate_and_process_data`: Every 60 minutes (India), 120 minutes (USA)
- `generate_trending_stocks_data`: Every 90 minutes (India), 180 minutes (USA)

## Error Handling

- HTTP exceptions for validation errors
- Graceful degradation when services unavailable
- Fallback to cached data when possible
- Comprehensive error logging

## Performance Optimizations

- Caching for similar queries
- Parallel API calls where possible
- Streaming responses for long operations
- Background tasks for non-critical operations
- Vector store indexing for fast retrieval

