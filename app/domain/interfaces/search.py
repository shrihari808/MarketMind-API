"""
Search Engine Abstract Interface.
Defines the contract for all external search providers (DuckDuckGo, Tavily, Brave).
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.schemas.rag import SourceCitation


class SearchEngine(ABC):
    """Abstract Base Class for web and news search providers."""

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
        country: str = "IN",
        timelimit: Optional[str] = None
    ) -> List[SourceCitation]:
        """Performs a general web search."""
        pass

    @abstractmethod
    async def search_news(
        self,
        query: str,
        max_results: int = 5,
        country: str = "IN",
        timelimit: Optional[str] = None
    ) -> List[SourceCitation]:
        """Performs a recency-focused news search."""
        pass
