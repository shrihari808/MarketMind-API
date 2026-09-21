"""
Infrastructure Adapters Package.
Exports all concrete implementations of the domain interfaces.
"""

from app.infrastructure.search.duckduckgo import DuckDuckGoSearcher
from app.infrastructure.scrapers.web_scraper import TrafilaturaWebScraper
from app.infrastructure.market.yfinance_client import YFinanceMarketClient
from app.infrastructure.llm.gemini import GeminiLLMClient
from app.infrastructure.vector_store.lance_store import LanceVectorStore

__all__ = [
    "DuckDuckGoSearcher",
    "TrafilaturaWebScraper",
    "YFinanceMarketClient",
    "GeminiLLMClient",
    "LanceVectorStore",
]
