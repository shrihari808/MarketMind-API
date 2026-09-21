"""
Serper Search Engine Adapter.
Provides Google search and news results via the Serper.dev API.
"""

import re
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlparse
import httpx

from app.core.config import get_settings
from app.core.logging import logger
from app.domain.interfaces.search import SearchEngine
from app.domain.schemas.rag import SourceCitation


def _parse_serper_date(date_str: Optional[str]) -> Optional[str]:
    """Parses relative or absolute date strings from Serper into ISO format."""
    if not date_str:
        return None

    date_str = date_str.strip()

    # Relative format: "2 hours ago", "3 days ago", "1 month ago"
    relative_match = re.match(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", date_str, re.IGNORECASE)
    if relative_match:
        val = int(relative_match.group(1))
        unit = relative_match.group(2).lower()
        now = datetime.now()

        if unit == "minute":
            delta = timedelta(minutes=val)
        elif unit == "hour":
            delta = timedelta(hours=val)
        elif unit == "day":
            delta = timedelta(days=val)
        elif unit == "week":
            delta = timedelta(weeks=val)
        elif unit == "month":
            delta = timedelta(days=val * 30)
        else:
            delta = timedelta(0)

        return (now - delta).strftime("%Y-%m-%d")

    # Absolute formats
    for fmt in ("%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str


class SerperSearcher(SearchEngine):
    """Google Search provider via Serper.dev API."""

    BASE_URL = "https://google.serper.dev"

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: int = 10):
        settings = get_settings()
        self.api_key = api_key or settings.SERPER_API_KEY
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
        """Performs a general web search via Serper."""
        if not self.api_key:
            logger.warning("SERPER_API_KEY is not configured. Returning empty search results.")
            return []

        url = f"{self.BASE_URL}/search"
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query,
            "num": max_results,
            "gl": country.lower()
        }

        logger.info(f"Executing Serper web search: '{query}' (gl={country.lower()})")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    logger.error(f"Serper API error: HTTP {response.status_code} - {response.text}")
                    return []

                data = response.json()
                items = data.get("organic", [])
                citations: List[SourceCitation] = []

                for i, item in enumerate(items[:max_results], start=1):
                    link = item.get("link", "")
                    if not link:
                        continue
                    citations.append(
                        SourceCitation(
                            id=i,
                            title=item.get("title", "Untitled Source"),
                            url=link,
                            snippet=item.get("snippet", ""),
                            publication_date=_parse_serper_date(item.get("date")),
                            domain=self._extract_domain(link),
                        )
                    )
                logger.info(f"Serper web search returned {len(citations)} citations")
                return citations

        except Exception as e:
            logger.error(f"Serper search error: {e}")
            return []

    async def search_news(
        self,
        query: str,
        max_results: int = 5,
        country: str = "IN"
    ) -> List[SourceCitation]:
        """Performs a recency-focused news search via Serper."""
        if not self.api_key:
            logger.warning("SERPER_API_KEY is not configured. Returning empty news results.")
            return []

        url = f"{self.BASE_URL}/news"
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query,
            "num": max_results,
            "gl": country.lower()
        }

        logger.info(f"Executing Serper news search: '{query}' (gl={country.lower()})")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    logger.error(f"Serper News API error: HTTP {response.status_code} - {response.text}")
                    return []

                data = response.json()
                items = data.get("news", [])
                citations: List[SourceCitation] = []

                for i, item in enumerate(items[:max_results], start=1):
                    link = item.get("link", "")
                    if not link:
                        continue
                    citations.append(
                        SourceCitation(
                            id=i,
                            title=item.get("title", "Untitled News"),
                            url=link,
                            snippet=item.get("snippet", ""),
                            publication_date=_parse_serper_date(item.get("date")),
                            domain=self._extract_domain(link),
                        )
                    )
                logger.info(f"Serper news search returned {len(citations)} articles")
                return citations

        except Exception as e:
            logger.error(f"Serper news search error: {e}")
            return []
