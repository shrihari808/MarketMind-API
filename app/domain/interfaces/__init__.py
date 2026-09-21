"""
Domain Interfaces Package.
Defines abstract contracts for external dependencies according to the Dependency Inversion Principle.
"""

from app.domain.interfaces.search import SearchEngine
from app.domain.interfaces.scraper import WebScraper
from app.domain.interfaces.market import MarketDataClient
from app.domain.interfaces.llm import LLMClient
from app.domain.interfaces.vector_store import VectorStore

__all__ = [
    "SearchEngine",
    "WebScraper",
    "MarketDataClient",
    "LLMClient",
    "VectorStore",
]
