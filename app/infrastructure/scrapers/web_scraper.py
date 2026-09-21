"""
Async Web Scraper Adapter.
Extracts clean article content using httpx and trafilatura with strict timeouts and concurrency.
"""

import asyncio
from typing import List, Optional
import httpx
import trafilatura
from app.core.logging import logger
from app.domain.interfaces.scraper import WebScraper
from app.domain.schemas.rag import ScrapedDocument


class TrafilaturaWebScraper(WebScraper):
    """Asynchronous article content scraper using httpx and trafilatura."""

    def __init__(self, timeout_seconds: int = 8):
        self.timeout = timeout_seconds
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def scrape(self, url: str) -> ScrapedDocument:
        """Asynchronously fetches a URL and extracts clean article text."""
        if not url or not url.startswith(("http://", "https://")):
            return ScrapedDocument(url=url, success=False, error="Invalid URL format")

        try:
            async with httpx.AsyncClient(
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=True,
                verify=False
            ) as client:
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

                html_content = response.text

            # Run CPU-bound trafilatura extraction in background thread
            extracted_text = await asyncio.to_thread(
                trafilatura.extract,
                html_content,
                include_comments=False,
                include_tables=True,
                no_fallback=False
            )

            if not extracted_text or len(extracted_text.strip()) < 50:
                return ScrapedDocument(
                    url=url,
                    success=False,
                    error="Content too short or could not be extracted"
                )

            return ScrapedDocument(
                url=url,
                content=extracted_text.strip(),
                success=True
            )

        except httpx.TimeoutException:
            logger.warning(f"Timeout scraping URL: {url}")
            return ScrapedDocument(url=url, success=False, error="Request timed out")
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return ScrapedDocument(url=url, success=False, error=str(e))

    async def scrape_many(self, urls: List[str]) -> List[ScrapedDocument]:
        """Concurrently scrapes multiple URLs with asyncio.gather."""
        if not urls:
            return []

        logger.info(f"Concurrently scraping {len(urls)} URLs...")
        tasks = [self.scrape(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        successful = sum(1 for r in results if r.success)
        logger.info(f"Scraped {len(urls)} URLs: {successful} successful, {len(urls) - successful} failed")
        return list(results)
