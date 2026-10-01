"""
DuckDuckGo Search Engine Adapter.
Provides zero-cost, API-key-free web and financial news search using DuckDuckGo.
"""

import asyncio
import re
from typing import List, Optional
from urllib.parse import urlparse

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from app.core.config import get_settings
from app.core.logging import logger
from app.domain.interfaces.search import SearchEngine
from app.domain.schemas.rag import SourceCitation


def _extract_date_from_url(url: str) -> Optional[str]:
    """Attempts to extract a YYYY-MM-DD date encoded in article URLs."""
    if not url:
        return None
    # Matches patterns like /2026/09/28/ or /2026-09-28/
    match = re.search(r"/(?P<y>202\d)[/-](?P<m>0[1-9]|1[0-2])[/-](?P<d>0[1-9]|[12]\d|3[01])", url)
    if match:
        return f"{match.group('y')}-{match.group('m')}-{match.group('d')}"
    return None


def _extract_date_from_snippet(snippet: str) -> Optional[str]:
    """Attempts to extract date prefixes commonly prepended in DDG text search snippets."""
    if not snippet:
        return None
    # Matches: 'Sep 28, 2026 ...' or 'September 28, 2026 -'
    match = re.search(
        r"^(?P<month>[A-Za-z]{3,9})\s+(?P<day>\d{1,2}),\s+(?P<year>202\d)\b",
        snippet.strip()
    )
    if match:
        from datetime import datetime
        raw_date = f"{match.group('month')} {match.group('day')}, {match.group('year')}"
        for fmt in ("%b %d, %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


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
        country: str = "IN",
        timelimit: Optional[str] = None
    ) -> List[SourceCitation]:
        """Performs a general web search via DuckDuckGo with freshness control and fallback."""
        settings = get_settings()
        effective_timelimit = timelimit if timelimit is not None else settings.SEARCH_TIMELIMIT
        region = self._get_region(country)
        logger.info(f"Executing DuckDuckGo web search: '{query}' (region={region}, timelimit={effective_timelimit})")

        def _sync_search() -> List[dict]:
            with DDGS() as ddgs:
                # 1. Primary search with specified timelimit
                res = list(ddgs.text(query, region=region, timelimit=effective_timelimit, max_results=max_results))
                # 2. If limited and empty, fallback to past year
                if not res and effective_timelimit in ("d", "w", "m"):
                    res = list(ddgs.text(query, region=region, timelimit="y", max_results=max_results))
                # 3. Fallback to unconstrained worldwide search
                if not res:
                    res = list(ddgs.text(query, region=None, timelimit=None, max_results=max_results))
                return res

        try:
            results = await asyncio.to_thread(_sync_search)
            citations: List[SourceCitation] = []
            for i, item in enumerate(results, start=1):
                url = item.get("href") or item.get("link", "")
                if not url:
                    continue
                snippet = item.get("body", "")
                pub_date = _extract_date_from_url(url) or _extract_date_from_snippet(snippet)
                citations.append(
                    SourceCitation(
                        id=i,
                        title=item.get("title", "Untitled Source"),
                        url=url,
                        snippet=snippet,
                        publication_date=pub_date,
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
        country: str = "IN",
        timelimit: Optional[str] = None
    ) -> List[SourceCitation]:
        """Performs a recency-focused news search via DuckDuckGo with progressive time fallback."""
        settings = get_settings()
        effective_timelimit = timelimit if timelimit is not None else settings.SEARCH_TIMELIMIT
        region = self._get_region(country)
        logger.info(f"Executing DuckDuckGo news search: '{query}' (region={region}, timelimit={effective_timelimit})")

        def _sync_news() -> List[dict]:
            with DDGS() as ddgs:
                # 1. Primary news search with requested timelimit
                res = list(ddgs.news(query, region=region, timelimit=effective_timelimit, max_results=max_results))
                # 2. Tiered fallback: if past day/week returned < 3 results, expand to past month
                if len(res) < 3 and effective_timelimit in ("d", "w"):
                    res = list(ddgs.news(query, region=region, timelimit="m", max_results=max_results))
                # 3. Fallback to unconstrained news if still empty
                if not res:
                    res = list(ddgs.news(query, region=None, timelimit=None, max_results=max_results))
                return res

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
