"""
Async Web Scraper Adapter.
Extracts clean article content using httpx and trafilatura with strict timeouts and concurrency.
"""

import asyncio
from typing import List, Optional
import httpx
import trafilatura
from app.core.cache import get_ttl_cache
from app.core.config import get_settings
from app.core.logging import logger
from app.domain.interfaces.scraper import WebScraper
from app.domain.schemas.rag import ScrapedDocument


class TrafilaturaWebScraper(WebScraper):
    """Asynchronous article content scraper using httpx, trafilatura, semaphore concurrency, and TTL caching."""

    def __init__(
        self,
        timeout_seconds: Optional[float] = None,
        max_concurrency: Optional[int] = None,
        cache_ttl_seconds: Optional[int] = None,
    ):
        settings = get_settings()
        self.timeout = float(timeout_seconds if timeout_seconds is not None else settings.SCRAPER_TIMEOUT_SECONDS)
        self.max_concurrency = max(1, int(max_concurrency if max_concurrency is not None else settings.SCRAPER_MAX_CONCURRENCY))
        self.cache_ttl_seconds = int(cache_ttl_seconds if cache_ttl_seconds is not None else settings.SCRAPER_CACHE_TTL_SECONDS)
        self._cache = get_ttl_cache("scraped_articles", max_entries=512, redis_url=settings.REDIS_URL)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    @staticmethod
    def _extract_markdown_tables(html_content: str) -> List[str]:
        """Extracts HTML tables and formats them as standard Markdown tables."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")
            tables = soup.find_all("table")
            markdown_tables = []

            for table in tables:
                rows = []
                for tr in table.find_all("tr"):
                    cells = [c.get_text(separator=" ", strip=True) for c in tr.find_all(["th", "td"])]
                    if cells and any(cells):
                        rows.append("| " + " | ".join(cells) + " |")
                if len(rows) >= 2:
                    header_cols = len(rows[0].split("|")) - 2
                    if header_cols > 0:
                        separator = "| " + " | ".join(["---"] * header_cols) + " |"
                        rows.insert(1, separator)
                        markdown_tables.append("\n".join(rows))

            return markdown_tables
        except Exception as e:
            logger.debug(f"Table extraction notice: {e}")
            return []

    async def _scrape_with_client(self, url: str, client: httpx.AsyncClient) -> ScrapedDocument:
        """Fetches and extracts clean article text using an existing httpx client under a hard timeout."""
        if not url or not url.startswith(("http://", "https://")):
            return ScrapedDocument(url=url, success=False, error="Invalid URL format")

        if self.cache_ttl_seconds > 0:
            cached = await self._cache.get(url)
            if cached is not None:
                return ScrapedDocument(**cached)

        max_bytes = 5 * 1024 * 1024  # 5 MB limit

        async def _do_scrape() -> ScrapedDocument:
            response = await client.get(url)
            if response.status_code != 200:
                return ScrapedDocument(
                    url=url,
                    success=False,
                    error=f"HTTP status {response.status_code}"
                )

            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                return ScrapedDocument(
                    url=url,
                    success=False,
                    error=f"Unsupported content type: {content_type}"
                )

            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                return ScrapedDocument(
                    url=url,
                    success=False,
                    error=f"Payload exceeds memory limit ({content_length} bytes)"
                )

            html_content = response.text
            final_url = str(response.url)
            if final_url != url:
                logger.debug(f"Followed redirect: {url} -> {final_url}")

            extracted_text, metadata = await asyncio.gather(
                asyncio.to_thread(
                    trafilatura.extract,
                    html_content,
                    include_comments=False,
                    include_tables=True,
                    no_fallback=False
                ),
                asyncio.to_thread(trafilatura.extract_metadata, html_content)
            )

            tables = await asyncio.to_thread(self._extract_markdown_tables, html_content)

            combined_content = (extracted_text or "").strip()
            if tables:
                table_section = "\n\n### Extracted Data Tables:\n" + "\n\n".join(tables[:5])
                combined_content += table_section

            published_date = metadata.date if metadata else None
            extracted_title = metadata.title if metadata and metadata.title else ""

            if not combined_content or len(combined_content.strip()) < 50:
                return ScrapedDocument(
                    url=url,
                    title=extracted_title,
                    published_date=published_date,
                    success=False,
                    error="Content too short or could not be extracted"
                )

            doc = ScrapedDocument(
                url=final_url,
                title=extracted_title,
                content=combined_content.strip(),
                published_date=published_date,
                success=True
            )
            if self.cache_ttl_seconds > 0:
                await self._cache.set(url, doc.model_dump(), self.cache_ttl_seconds)
            return doc

        try:
            return await asyncio.wait_for(_do_scrape(), timeout=self.timeout)
        except (httpx.TimeoutException, asyncio.TimeoutError):
            logger.warning(f"Timeout scraping URL ({self.timeout}s): {url}")
            return ScrapedDocument(url=url, success=False, error=f"Timed out after {self.timeout}s")
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return ScrapedDocument(url=url, success=False, error=str(e))

    async def scrape(self, url: str) -> ScrapedDocument:
        """Asynchronously fetches a URL and extracts clean article text."""
        if not url or not url.startswith(("http://", "https://")):
            return ScrapedDocument(url=url, success=False, error="Invalid URL format")

        if self.cache_ttl_seconds > 0:
            cached = await self._cache.get(url)
            if cached is not None:
                return ScrapedDocument(**cached)

        http_timeout = httpx.Timeout(self.timeout, connect=min(1.5, self.timeout))
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=http_timeout,
            follow_redirects=True,
            max_redirects=5,
            verify=False,
        ) as client:
            return await self._scrape_with_client(url, client)

    async def scrape_many(self, urls: List[str]) -> List[ScrapedDocument]:
        """Concurrently scrapes multiple URLs with a shared connection pool, semaphore, and hard timeout."""
        if not urls:
            return []

        logger.info(f"Concurrently scraping {len(urls)} URLs (timeout={self.timeout}s, max_concurrency={self.max_concurrency})...")
        semaphore = asyncio.Semaphore(self.max_concurrency)
        http_timeout = httpx.Timeout(self.timeout, connect=min(1.5, self.timeout))
        limits = httpx.Limits(max_connections=self.max_concurrency, max_keepalive_connections=self.max_concurrency)

        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=http_timeout,
            limits=limits,
            follow_redirects=True,
            max_redirects=5,
            verify=False,
        ) as client:
            async def _bounded(u: str) -> ScrapedDocument:
                async with semaphore:
                    return await self._scrape_with_client(u, client)

            results = await asyncio.gather(*[_bounded(u) for u in urls], return_exceptions=False)

        successful = sum(1 for r in results if r.success)
        logger.info(f"Scraped {len(urls)} URLs: {successful} successful, {len(urls) - successful} failed")
        return list(results)
