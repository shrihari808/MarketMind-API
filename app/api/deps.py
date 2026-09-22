"""
FastAPI Dependency Injection Layer.
Provides injectable dependencies for database sessions, anonymous client identity,
external service adapters, and domain RAG orchestrators.
"""

from typing import AsyncGenerator, Optional
from fastapi import Request, Query, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import verify_api_key
from app.domain.interfaces.llm import LLMClient
from app.domain.interfaces.market import MarketDataClient
from app.domain.interfaces.search import SearchEngine
from app.domain.interfaces.scraper import WebScraper

from app.infrastructure.llm.gemini import GeminiLLMClient
from app.infrastructure.market.yfinance_client import YFinanceMarketClient
from app.infrastructure.search.factory import SearchEngineFactory
from app.infrastructure.scrapers.web_scraper import TrafilaturaWebScraper

from app.services.web_rag import WebRAGService
from app.services.document_rag import DocumentRAGService
from app.services.reddit_rag import RedditRAGService
from app.services.dashboard import MarketDashboardService
from app.services.deep_research import DeepResearchService


# --- Anonymous Client Identity Dependency ---

def get_client_id(
    request: Request,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-ID"),
    client_id: Optional[str] = Query(default=None, alias="client_id")
) -> str:
    """
    Extracts the anonymous browser client UUID.
    Checks:
    1. 'X-Client-ID' HTTP header
    2. 'client_id' query parameter
    3. Fallback to 'anonymous_client'
    """
    if x_client_id and x_client_id.strip():
        return x_client_id.strip()
    if client_id and client_id.strip():
        return client_id.strip()
    return "anonymous_client"


# --- Database Dependency ---

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields an active asynchronous SQLAlchemy session."""
    async for session in get_db_session():
        yield session


# --- Infrastructure Adapters ---

def get_llm_client() -> LLMClient:
    """Provides the Gemini LLM client instance."""
    return GeminiLLMClient()


def get_market_client() -> MarketDataClient:
    """Provides the YFinance market data client instance."""
    return YFinanceMarketClient()


def get_search_engine() -> SearchEngine:
    """Provides the configured search engine instance (DuckDuckGo/Serper/Brave)."""
    return SearchEngineFactory.create()


def get_scraper() -> WebScraper:
    """Provides the lightweight HTML scraper with table extraction."""
    return TrafilaturaWebScraper()


# --- Business Services Dependencies ---

def get_web_rag_service(
    llm: LLMClient = Depends(get_llm_client),
    search: SearchEngine = Depends(get_search_engine),
    scraper: WebScraper = Depends(get_scraper),
    market: MarketDataClient = Depends(get_market_client)
) -> WebRAGService:
    """Injects configured WebRAGService."""
    return WebRAGService(
        llm_client=llm,
        search_engine=search,
        scraper=scraper,
        market_client=market
    )


def get_document_rag_service(
    llm: LLMClient = Depends(get_llm_client)
) -> DocumentRAGService:
    """Injects configured DocumentRAGService."""
    return DocumentRAGService(llm_client=llm)


def get_reddit_rag_service(
    llm: LLMClient = Depends(get_llm_client),
    search: SearchEngine = Depends(get_search_engine),
    scraper: WebScraper = Depends(get_scraper)
) -> RedditRAGService:
    """Injects configured RedditRAGService."""
    return RedditRAGService(
        llm_client=llm,
        search_engine=search,
        scraper=scraper
    )


def get_dashboard_service(
    market: MarketDataClient = Depends(get_market_client),
    llm: LLMClient = Depends(get_llm_client)
) -> MarketDashboardService:
    """Injects configured MarketDashboardService."""
    return MarketDashboardService(
        market_client=market,
        llm_client=llm
    )


def get_deep_research_service(
    llm: LLMClient = Depends(get_llm_client),
    market: MarketDataClient = Depends(get_market_client),
    search: SearchEngine = Depends(get_search_engine),
    scraper: WebScraper = Depends(get_scraper)
) -> DeepResearchService:
    """Injects configured DeepResearchService."""
    return DeepResearchService(
        llm_client=llm,
        market_client=market,
        search_engine=search,
        scraper=scraper
    )
