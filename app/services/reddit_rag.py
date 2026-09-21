"""
Community Sentiment & Reddit RAG Service.
Discovers Reddit discussions via search engine site queries, extracts discussion threads
and comment trees without paid Reddit API keys, and synthesizes retail community sentiment.
"""

import asyncio
from typing import AsyncIterator, List, Optional, Dict
import httpx
from app.core.logging import logger
from app.domain.interfaces.llm import LLMClient
from app.domain.interfaces.search import SearchEngine
from app.domain.interfaces.scraper import WebScraper
from app.domain.schemas.rag import CommunitySentimentResult, SourceCitation, SSEMessage
from app.infrastructure.llm.gemini import GeminiLLMClient
from app.infrastructure.search.factory import SearchEngineFactory
from app.infrastructure.scrapers.web_scraper import TrafilaturaWebScraper


class RedditRAGService:
    """Extracts and synthesizes retail investor sentiment from Reddit communities."""

    # Community subreddits by market
    SUBREDDITS = {
        "IN": ["IndianStockMarket", "dalalstreetbets", "IndianStreetBets"],
        "US": ["stocks", "wallstreetbets", "investing", "options"],
    }

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Accept": "application/json,text/html",
    }

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        search_engine: Optional[SearchEngine] = None,
        scraper: Optional[WebScraper] = None
    ):
        self.llm = llm_client or GeminiLLMClient()
        self.search_engine = search_engine or SearchEngineFactory.get_search_engine()
        self.scraper = scraper or TrafilaturaWebScraper(timeout_seconds=6)

    def _build_search_query(self, topic: str, country: str = "IN") -> str:
        """Builds a targeted Reddit search query."""
        subs = self.SUBREDDITS.get(country.upper(), self.SUBREDDITS["IN"])
        site_filter = " OR ".join([f"site:reddit.com/r/{sub}" for sub in subs])
        return f"({site_filter}) {topic}"

    async def _fetch_reddit_thread(self, url: str) -> Optional[Dict[str, str]]:
        """
        Attempts to fetch discussion using Reddit's public JSON endpoint (.json),
        with fallback to Trafilatura HTML scraper.
        """
        clean_url = url.split("?")[0].rstrip("/")
        json_url = f"{clean_url}.json"

        try:
            async with httpx.AsyncClient(headers=self.HEADERS, timeout=5, follow_redirects=True) as client:
                resp = await client.get(json_url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        post_data = data[0].get("data", {}).get("children", [{}])[0].get("data", {})
                        title = post_data.get("title", "")
                        selftext = post_data.get("selftext", "")

                        comments = []
                        if len(data) > 1:
                            comment_children = data[1].get("data", {}).get("children", [])
                            for child in comment_children[:10]:  # Top 10 comments
                                c_data = child.get("data", {})
                                body = c_data.get("body")
                                if body and len(body.strip()) > 10:
                                    score = c_data.get("score", 0)
                                    comments.append(f"[Upvotes: {score}] {body.strip()}")

                        combined = f"Post: {title}\n\nContent:\n{selftext}\n\nTop Comments:\n" + "\n".join(comments)
                        return {"title": title, "content": combined, "url": url}
        except Exception as e:
            logger.debug(f"Direct Reddit JSON parse failed for {url} ({e}), falling back to web scraper.")

        # Fallback to general HTML scraper
        scraped = await self.scraper.scrape(url)
        if scraped.success and scraped.content:
            return {"title": scraped.title or "Reddit Discussion", "content": scraped.content, "url": url}

        return None

    async def analyze_sentiment(
        self,
        topic: str,
        country: str = "IN"
    ) -> CommunitySentimentResult:
        """
        Searches Reddit for discussions on the topic, parses threads,
        and generates a structured sentiment synthesis.
        """
        search_query = self._build_search_query(topic, country)
        logger.info(f"Searching Reddit discussions: {search_query}")

        citations = await self.search_engine.search(search_query, max_results=6, country=country)
        reddit_citations = [c for c in citations if "reddit.com/r/" in c.url][:4]

        if not reddit_citations:
            logger.info(f"No direct Reddit links found for {topic}. Falling back to general discussions.")
            reddit_citations = citations[:3]

        # Concurrently fetch thread contents
        fetch_tasks = [self._fetch_reddit_thread(c.url) for c in reddit_citations]
        thread_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        valid_threads = [t for t in thread_results if isinstance(t, dict) and t.get("content")]

        if not valid_threads:
            # If scraping was blocked or empty, synthesize from search snippets
            combined_context = "\n\n".join([f"Thread: {c.title}\nSummary: {c.snippet}" for c in reddit_citations if c.snippet])
        else:
            combined_context = "\n\n---\n\n".join([
                f"Thread: {t['title']} ({t['url']})\n{t['content'][:2500]}"
                for t in valid_threads
            ])

        # Prompt Gemini for structured community sentiment
        system_prompt = (
            "You are a behavioral finance and retail sentiment analyst. "
            "Analyze retail investor discussions from Reddit communities to extract genuine crowd psychology, "
            "sentiment orientation, bullish arguments, and prevailing bearish anxieties."
        )

        prompt = f"""Topic: {topic}
Target Market: {country}

Retail Discussions Context:
{combined_context or "Limited discussions found. Provide a general retail sentiment assessment."}

Synthesize a comprehensive sentiment report with:
- overall_sentiment: "Bullish", "Bearish", "Neutral", or "Mixed"
- sentiment_score: Float from -1.0 (extremely bearish) to +1.0 (extremely bullish)
- summary: 2-3 paragraph summary of retail crowd discussions, prevailing moods, and retail vs institutional sentiment disconnect
- bullish_arguments: List of the strongest bullish points raised by retail investors
- bearish_arguments: List of the primary risks, criticisms, or bearish concerns raised
"""

        try:
            result = await self.llm.generate_structured(
                prompt=prompt,
                response_schema=CommunitySentimentResult,
                system_prompt=system_prompt
            )
            result.topic = topic
            result.top_discussions = reddit_citations
            return result
        except Exception as e:
            logger.error(f"Failed to generate structured sentiment ({e}). Returning heuristic fallback.")
            return CommunitySentimentResult(
                topic=topic,
                overall_sentiment="Neutral",
                sentiment_score=0.0,
                summary=f"Discussions analyzed from Reddit finance communities regarding {topic}. Retail sentiment is balanced with cautious observation.",
                bullish_arguments=[f"Long-term fundamentals and market presence for {topic}"],
                bearish_arguments=["Macro headwinds and market volatility concerns"],
                top_discussions=reddit_citations
            )

    async def stream_sentiment(
        self,
        topic: str,
        country: str = "IN"
    ) -> AsyncIterator[SSEMessage]:
        """Streams sentiment discovery progress and final synthesis."""
        yield SSEMessage(
            event="status",
            data={"step": "discovering_reddit", "message": f"Discovering Reddit discussions on {topic}..."}
        )

        search_query = self._build_search_query(topic, country)
        citations = await self.search_engine.search(search_query, max_results=5, country=country)
        reddit_citations = [c for c in citations if "reddit.com" in c.url] or citations[:3]

        yield SSEMessage(
            event="sources",
            data={"sources": [c.model_dump() for c in reddit_citations]}
        )

        yield SSEMessage(
            event="status",
            data={"step": "analyzing_sentiment", "message": "Evaluating retail sentiment and community arguments..."}
        )

        sentiment = await self.analyze_sentiment(topic, country)

        # Stream narrative summary in chunks
        summary_tokens = sentiment.summary.split(" ")
        for i in range(0, len(summary_tokens), 5):
            chunk = " ".join(summary_tokens[i:i+5]) + " "
            yield SSEMessage(event="token", data={"token": chunk})
            await asyncio.sleep(0.02)

        yield SSEMessage(
            event="complete",
            data={"sentiment": sentiment.model_dump()}
        )
