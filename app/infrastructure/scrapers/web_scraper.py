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

    async def scrape(self, url: str) -> ScrapedDocument:
        """Asynchronously fetches a URL and extracts clean article text."""
        if not url or not url.startswith(("http://", "https://")):
            return ScrapedDocument(url=url, success=False, error="Invalid URL format")

        # Guard against gigantic downloads to protect 512MB RAM
        max_bytes = 5 * 1024 * 1024  # 5 MB limit

        try:
            async with httpx.AsyncClient(
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=True,
                max_redirects=5,
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

                # Memory guard: enforce size limit
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

            # Run CPU-bound trafilatura extraction in background thread
            extracted_text = await asyncio.to_thread(
                trafilatura.extract,
                html_content,
                include_comments=False,
                include_tables=True,
                no_fallback=False
            )

            # Extract any structured HTML tables as clean Markdown
            tables = await asyncio.to_thread(self._extract_markdown_tables, html_content)
            
            combined_content = (extracted_text or "").strip()
            if tables:
                table_section = "\n\n### Extracted Data Tables:\n" + "\n\n".join(tables[:5])  # Cap at top 5 tables
                combined_content += table_section

            if not combined_content or len(combined_content.strip()) < 50:
                return ScrapedDocument(
                    url=url,
                    success=False,
                    error="Content too short or could not be extracted"
                )

            return ScrapedDocument(
                url=final_url,
                content=combined_content.strip(),
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
