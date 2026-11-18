"""
Brave Search Engine Adapter.
Provides web and financial news search using the Brave Search API.
"""

import asyncio
import time
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse
from weakref import WeakKeyDictionary
import httpx

from app.core.config import get_settings
from app.core.logging import logger
from app.domain.interfaces.search import SearchEngine
from app.domain.schemas.rag import SourceCitation


def _parse_brave_date(page_age: Optional[str]) -> Optional[str]:
    """Parses Brave page_age timestamp into a simple YYYY-MM-DD string."""
    if not page_age:
        return None
    try:
        clean_date = page_age.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_date)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(page_age)[:10]


def _map_brave_freshness(timelimit: Optional[str]) -> Optional[str]:
    """Maps standard timelimit ('d', 'w', 'm', 'y') to Brave freshness ('pd', 'pw', 'pm', 'py')."""
    if not timelimit:
        return None
    mapping = {
        "d": "pd",
        "w": "pw",
        "m": "pm",
        "y": "py",
    }
    return mapping.get(timelimit.lower())


class BraveSearcher(SearchEngine):
    """Brave Search API provider implementing the SearchEngine protocol with free-tier rate spacing."""

    BASE_URL = "https://api.search.brave.com/res/v1/web/search"
    _rate_locks: WeakKeyDictionary = WeakKeyDictionary()
    _last_request_ts: float = 0.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout_seconds: int = 10,
        min_interval_seconds: Optional[float] = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.BRAVE_API_KEY
        self.timeout = timeout_seconds
        self.min_interval = (
            float(min_interval_seconds)
            if min_interval_seconds is not None
            else float(settings.BRAVE_MIN_INTERVAL_SECONDS)
        )

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        lock = cls._rate_locks.get(loop)
        if lock is None:
            lock = asyncio.Lock()
            cls._rate_locks[loop] = lock
        return lock

    async def _throttled_get(self, headers: dict, params: dict) -> httpx.Response:
        """Spaces Brave API requests by min_interval to respect free-tier 1 req/s limits."""
        lock = self._get_lock()
        async with lock:
            if self.min_interval > 0:
                elapsed = time.monotonic() - BraveSearcher._last_request_ts
                if elapsed < self.min_interval:
                    await asyncio.sleep(self.min_interval - elapsed)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.BASE_URL, headers=headers, params=params)
            BraveSearcher._last_request_ts = time.monotonic()

            # Single spaced retry on 429 Too Many Requests
            if response.status_code == 429:
                retry_wait = max(self.min_interval, 1.1)
                logger.warning(f"Brave Search hit HTTP 429; retrying once after {retry_wait:.2f}s...")
                await asyncio.sleep(retry_wait)
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(self.BASE_URL, headers=headers, params=params)
                BraveSearcher._last_request_ts = time.monotonic()
            return response

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
        """Performs general web search via Brave Search API with optional freshness filter."""
        if not self.api_key:
            logger.warning("BRAVE_API_KEY is not configured. Returning empty search results.")
            return []

        settings = get_settings()
        effective_timelimit = timelimit if timelimit is not None else settings.SEARCH_TIMELIMIT
        freshness = _map_brave_freshness(effective_timelimit)

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key
        }
        params = {
            "q": query,
            "count": min(max_results, 20),
            "country": country.lower(),
            "result_filter": "web"
        }
        if freshness:
            params["freshness"] = freshness

        logger.info(f"Executing Brave web search: '{query}' (country={country.lower()}, freshness={freshness})")
        try:
            response = await self._throttled_get(headers, params)
            if response.status_code != 200:
                logger.error(f"Brave Search API error: HTTP {response.status_code} - {response.text}")
                return []

            data = response.json()
            items = data.get("web", {}).get("results", [])
            citations: List[SourceCitation] = []

            for i, item in enumerate(items[:max_results], start=1):
                url = item.get("url", "")
                if not url:
                    continue
                citations.append(
                    SourceCitation(
                        id=i,
                        title=item.get("title", "Untitled Source"),
                        url=url,
                        snippet=item.get("description", ""),
                        publication_date=_parse_brave_date(item.get("page_age")),
                        domain=self._extract_domain(url),
                    )
                )
            logger.info(f"Brave web search returned {len(citations)} citations")
            return citations

        except Exception as e:
            logger.error(f"Brave search error: {e}")
            return []

    async def search_news(
        self,
        query: str,
        max_results: int = 5,
        country: str = "IN",
        timelimit: Optional[str] = None
    ) -> List[SourceCitation]:
        """Performs recency-focused news search via Brave Search API with freshness control."""
        if not self.api_key:
            logger.warning("BRAVE_API_KEY is not configured. Returning empty news results.")
            return []

        settings = get_settings()
        effective_timelimit = timelimit if timelimit is not None else settings.SEARCH_TIMELIMIT
        # Default to 'pw' (past week) for news if not specified
        freshness = _map_brave_freshness(effective_timelimit) or "pw"

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key
        }
        params = {
            "q": query,
            "count": min(max_results, 20),
            "country": country.lower(),
            "result_filter": "news",
            "freshness": freshness
        }

        logger.info(f"Executing Brave news search: '{query}' (country={country.lower()}, freshness={freshness})")
        try:
            response = await self._throttled_get(headers, params)
            if response.status_code != 200:
                logger.error(f"Brave News Search API error: HTTP {response.status_code} - {response.text}")
                return []

            data = response.json()
            items = data.get("news", {}).get("results", [])
            # If news results are empty, fallback to web results
            if not items:
                items = data.get("web", {}).get("results", [])

            citations: List[SourceCitation] = []
            for i, item in enumerate(items[:max_results], start=1):
                url = item.get("url", "")
                if not url:
                    continue
                citations.append(
                    SourceCitation(
                        id=i,
                        title=item.get("title", "Untitled News"),
                        url=url,
                        snippet=item.get("description", ""),
                        publication_date=_parse_brave_date(item.get("page_age")),
                        domain=self._extract_domain(url),
                    )
                )
            logger.info(f"Brave news search returned {len(citations)} articles")
            return citations

        except Exception as e:
            logger.error(f"Brave news search error: {e}")
            return []
