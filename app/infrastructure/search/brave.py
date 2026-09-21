"""
Brave Search Engine Adapter.
Provides web and financial news search using the Brave Search API.
"""

from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse
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


class BraveSearcher(SearchEngine):
    """Brave Search API provider implementing the SearchEngine protocol."""

    BASE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: int = 10):
        settings = get_settings()
        self.api_key = api_key or settings.BRAVE_API_KEY
        self.timeout = timeout_seconds

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
        """Performs general web search via Brave Search API."""
        if not self.api_key:
            logger.warning("BRAVE_API_KEY is not configured. Returning empty search results.")
            return []

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

        logger.info(f"Executing Brave web search: '{query}' (country={country.lower()})")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.BASE_URL, headers=headers, params=params)
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
        country: str = "IN"
    ) -> List[SourceCitation]:
        """Performs recency-focused news search via Brave Search API."""
        if not self.api_key:
            logger.warning("BRAVE_API_KEY is not configured. Returning empty news results.")
            return []

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key
        }
        params = {
            "q": query,
            "count": min(max_results, 20),
            "country": country.lower(),
            "result_filter": "news",
            "freshness": "pd"  # past day for fresh financial news
        }

        logger.info(f"Executing Brave news search: '{query}' (country={country.lower()})")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.BASE_URL, headers=headers, params=params)
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
