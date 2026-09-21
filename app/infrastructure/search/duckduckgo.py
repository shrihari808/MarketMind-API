"""
DuckDuckGo Search Engine Adapter.
Provides zero-cost, API-key-free web and financial news search using DuckDuckGo.
"""

import asyncio
from typing import List
from urllib.parse import urlparse
from duckduckgo_search import DDGS
from app.core.logging import logger
from app.domain.interfaces.search import SearchEngine
from app.domain.schemas.rag import SourceCitation


class DuckDuckGoSearcher(SearchEngine):
    """Zero-cost search provider implementing the SearchEngine protocol."""

    def __init__(self):
        # Maps country codes to DuckDuckGo region identifiers
        self._region_map = {
            "IN": "in-en",
            "US": "us-en",
            "UK": "uk-en",
            "GB": "uk-en",
        }

    def _get_region(self, country: str) -> str:
        return self._region_map.get(country.upper(), "wt-wt")

    def _extract_domain(self, url: str) -> str:
        try:
            netloc = urlparse(url).netloc
            return netloc.replace("www.", "")
        except Exception:
            return ""

    async def search(
        self,
        query: str,
        max_results: int = 5,
        country: str = "IN"
    ) -> List[SourceCitation]:
        """Performs a general web search via DuckDuckGo in a separate thread."""
        region = self._get_region(country)
        logger.info(f"Executing DuckDuckGo web search: '{query}' (region={region})")

        def _sync_search() -> List[dict]:
            with DDGS() as ddgs:
                return list(ddgs.text(query, region=region, max_results=max_results))

        try:
            results = await asyncio.to_thread(_sync_search)
            citations: List[SourceCitation] = []
            for i, item in enumerate(results, start=1):
                url = item.get("href") or item.get("link", "")
                if not url:
                    continue
                citations.append(
                    SourceCitation(
                        id=i,
                        title=item.get("title", "Untitled Source"),
                        url=url,
                        snippet=item.get("body", ""),
                        domain=self._extract_domain(url),
                    )
                )
            logger.info(f"DuckDuckGo web search returned {len(citations)} citations")
            return citations
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return []

    async def search_news(
        self,
        query: str,
        max_results: int = 5,
        country: str = "IN"
    ) -> List[SourceCitation]:
        """Performs a recency-focused news search via DuckDuckGo."""
        region = self._get_region(country)
        logger.info(f"Executing DuckDuckGo news search: '{query}' (region={region})")

        def _sync_news() -> List[dict]:
            with DDGS() as ddgs:
                return list(ddgs.news(query, region=region, max_results=max_results))

        try:
            results = await asyncio.to_thread(_sync_news)
            citations: List[SourceCitation] = []
            for i, item in enumerate(results, start=1):
                url = item.get("url") or item.get("link", "")
                if not url:
                    continue
                citations.append(
                    SourceCitation(
                        id=i,
                        title=item.get("title", "Untitled News"),
                        url=url,
                        snippet=item.get("body", ""),
                        publication_date=item.get("date"),
                        domain=self._extract_domain(url),
                    )
                )
            logger.info(f"DuckDuckGo news search returned {len(citations)} articles")
            return citations
        except Exception as e:
            logger.error(f"DuckDuckGo news search error: {e}")
            return []
