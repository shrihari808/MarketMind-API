"""
Search Infrastructure Package.
Exposes SearchEngine adapters and the SearchEngineFactory.
"""

from app.domain.interfaces.search import SearchEngine
from app.infrastructure.search.duckduckgo import DuckDuckGoSearcher
from app.infrastructure.search.serper import SerperSearcher
from app.infrastructure.search.brave import BraveSearcher
from app.infrastructure.search.factory import SearchEngineFactory

__all__ = [
    "SearchEngine",
    "DuckDuckGoSearcher",
    "SerperSearcher",
    "BraveSearcher",
    "SearchEngineFactory",
]
