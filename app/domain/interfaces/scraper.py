"""
Web Scraper Abstract Interface.
Defines the contract for asynchronously extracting text content from URLs.
"""

from abc import ABC, abstractmethod
from typing import List
from app.domain.schemas.rag import ScrapedDocument


class WebScraper(ABC):
    """Abstract Base Class for web article scraping."""

    @abstractmethod
    async def scrape(self, url: str) -> ScrapedDocument:
        """Asynchronously scrapes a single URL and extracts clean article text."""
        pass

    @abstractmethod
    async def scrape_many(self, urls: List[str]) -> List[ScrapedDocument]:
        """Concurrently scrapes multiple URLs with timeout & error handling."""
        pass
