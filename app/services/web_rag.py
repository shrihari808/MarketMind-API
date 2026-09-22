"""
High-Performance Streaming Web RAG Service.
Coordinates query analysis, multi-angle search, parallel scraping,
BM25 passage reranking with domain diversification, and Gemini streaming synthesis.
"""

import asyncio
import time
from typing import AsyncIterator, List, Optional, Dict
from app.core.config import get_settings
from app.core.logging import logger
from app.domain.interfaces.llm import LLMClient
from app.domain.interfaces.market import MarketDataClient
from app.domain.interfaces.scraper import WebScraper
from app.domain.interfaces.search import SearchEngine
from app.domain.schemas.market import StockQuote
from app.domain.schemas.rag import (
    RAGQueryRequest,
    RAGResult,
    SourceCitation,
    ScrapedDocument,
    PassageChunk,
    SSEMessage,
)
from app.infrastructure.llm.gemini import GeminiLLMClient
from app.infrastructure.market.yfinance_client import YFinanceMarketClient
from app.infrastructure.scrapers.web_scraper import TrafilaturaWebScraper
from app.infrastructure.search.factory import SearchEngineFactory
from app.services.query_analyzer import QueryAnalyzer
from app.services.reranker import BM25Reranker, HybridReranker


class WebRAGService:
    """End-to-end financial Web RAG service adhering to Clean Architecture."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        search_engine: Optional[SearchEngine] = None,
        scraper: Optional[WebScraper] = None,
        market_client: Optional[MarketDataClient] = None,
        use_hybrid_reranker: bool = False
    ):
        settings = get_settings()
        self.llm = llm_client or GeminiLLMClient()
        self.search_engine = search_engine or SearchEngineFactory.get_search_engine()
        self.scraper = scraper or TrafilaturaWebScraper(timeout_seconds=settings.SCRAPER_TIMEOUT_SECONDS)
        self.market = market_client or YFinanceMarketClient()
        self.query_analyzer = QueryAnalyzer(llm_client=self.llm, market_client=self.market)

        if use_hybrid_reranker:
            self.reranker = HybridReranker(llm_client=self.llm)
        else:
            self.reranker = BM25Reranker()

    @staticmethod
    def _chunk_text(text: str, chunk_size: Optional[int] = None, overlap: Optional[int] = None) -> List[str]:
        """Splits document text into overlapping word chunks based on settings."""
        settings = get_settings()
        c_size = chunk_size or settings.RAG_CHUNK_SIZE
        o_lap = overlap or settings.RAG_CHUNK_OVERLAP

        words = text.split()
        if len(words) <= c_size:
            return [text]

        chunks = []
        start = 0
        while start < len(words):
            end = min(start + c_size, len(words))
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            if end >= len(words):
                break
            start += c_size - o_lap
        return chunks

    def _extract_passages(
        self,
        documents: List[ScrapedDocument],
        citations_map: Dict[str, SourceCitation]
    ) -> List[PassageChunk]:
        """Converts scraped documents into indexed passage chunks linked to source citations."""
        settings = get_settings()
        passages: List[PassageChunk] = []
        for doc in documents:
            if not doc.success or not doc.content:
                continue

            citation = citations_map.get(doc.url)
            if not citation:
                citation = next((c for u, c in citations_map.items() if u in doc.url or doc.url in u), None)

            if not citation:
                citation = SourceCitation(
                    id=len(citations_map) + 1,
                    title=doc.title or "Web Source",
                    url=doc.url,
                    domain=BM25Reranker.extract_domain(doc.url)
                )

            chunks = self._chunk_text(doc.content, chunk_size=settings.RAG_CHUNK_SIZE, overlap=settings.RAG_CHUNK_OVERLAP)
            for idx, text_chunk in enumerate(chunks[:8]):  # Cap at top 8 chunks per document
                passages.append(
                    PassageChunk(
                        text=text_chunk,
                        source=citation,
                        score=0.0,
                        chunk_index=idx
                    )
                )
        logger.info(f"[WebRAGService] Extracted {len(passages)} candidate passage chunks from {len(documents)} scraped document(s).")
        return passages

    async def stream(
        self,
        request: RAGQueryRequest,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncIterator[SSEMessage]:
        """
        Executes the Web RAG pipeline and yields standardized SSE messages.
        """
        settings = get_settings()
        start_time = time.time()
        logger.info(f"[WebRAGService] Incoming RAG query: '{request.query}' (country={request.country}, session_id={request.session_id})")

        # Step 1: Query Analysis & Financial Guardrail
        yield SSEMessage(event="status", data={"step": "analyzing_query", "message": "Analyzing financial query..."})
        
        analysis = await self.query_analyzer.analyze(
            query=request.query,
            country=request.country,
            chat_history=chat_history
        )

        if not analysis.is_financial:
            logger.info(f"[WebRAGService] Guardrail triggered: '{request.query}' rejected as non-financial.")
            yield SSEMessage(
                event="token",
                data={"token": f"I specialize in financial markets, equities, and economic intelligence. {analysis.financial_reason}\n\nPlease ask a question related to stocks, financial statements, or market trends."}
            )
            yield SSEMessage(
                event="complete",
                data={"tokens_used": 0, "duration_seconds": round(time.time() - start_time, 2)}
            )
            return

        # Step 2: Fetch Live Stock Quote if applicable
        quote_task = None
        if analysis.detected_ticker:
            logger.info(f"[WebRAGService] Ticker '{analysis.detected_ticker}' detected. Dispatching live quote fetch.")
            quote_task = asyncio.create_task(self.market.get_quote(analysis.detected_ticker))

        # Step 3: Multi-Query Search
        yield SSEMessage(event="status", data={"step": "searching", "message": "Searching financial news and web..."})
        search_queries = analysis.sub_queries or [request.query]
        max_search = settings.MAX_SEARCH_RESULTS
        per_query_limit = max(2, max_search // len(search_queries) + 1)
        logger.info(f"[WebRAGService] Dispatching search across {len(search_queries)} sub-queries (per_query_limit={per_query_limit})...")

        search_tasks = [
            self.search_engine.search_news(q, max_results=per_query_limit, country=request.country)
            for q in search_queries[:2]
        ] + [
            self.search_engine.search(search_queries[-1], max_results=per_query_limit, country=request.country)
        ]
        search_results_nested = await asyncio.gather(*search_tasks, return_exceptions=True)

        all_citations: List[SourceCitation] = []
        seen_urls = set()
        for res in search_results_nested:
            if isinstance(res, list):
                for item in res:
                    if item.url not in seen_urls:
                        seen_urls.add(item.url)
                        all_citations.append(item)

        # Cap citations and re-index
        top_citations = all_citations[:max_search]
        for idx, cit in enumerate(top_citations, start=1):
            cit.id = idx

        citations_map = {c.url: c for c in top_citations}
        logger.info(f"[WebRAGService] Found {len(all_citations)} unique search results. Filtered to top {len(top_citations)} citations.")

        # Step 4: Emit Citations to Client Early
        yield SSEMessage(
            event="sources",
            data={"sources": [c.model_dump() for c in top_citations]}
        )

        # Step 5: Concurrently Scrape Top URLs
        yield SSEMessage(event="status", data={"step": "reading_sources", "message": "Scraping and analyzing source articles..."})
        urls_to_scrape = [c.url for c in top_citations]
        logger.info(f"[WebRAGService] Scraping {len(urls_to_scrape)} URLs...")
        scraped_docs = await self.scraper.scrape_many(urls_to_scrape)

        # Step 6: Passage Extraction and BM25 Reranking
        passages = self._extract_passages(scraped_docs, citations_map)
        
        # If scraper failed to extract full text, build fallback passages from search snippets
        if not passages and top_citations:
            logger.info("[WebRAGService] No article bodies extracted. Falling back to search snippets for passage pool.")
            for c in top_citations:
                if c.snippet:
                    passages.append(
                        PassageChunk(
                            text=f"Title: {c.title}\n{c.snippet}",
                            source=c,
                            score=1.0,
                            chunk_index=0
                        )
                    )

        # Rerank and diversify passages
        logger.info(f"[WebRAGService] Reranking {len(passages)} passages...")
        if isinstance(self.reranker, HybridReranker):
            selected_passages = await self.reranker.rerank(
                query=request.query,
                passages=passages,
                top_k=5,
                max_per_domain=2
            )
        else:
            selected_passages = self.reranker.rerank(
                query=request.query,
                passages=passages,
                top_k=5,
                max_per_domain=2
            )

        # Await real-time quote if initiated
        live_quote: Optional[StockQuote] = None
        if quote_task:
            try:
                live_quote = await quote_task
                if live_quote:
                    logger.info(f"[WebRAGService] Live quote retrieved for {live_quote.ticker}: {live_quote.currency} {live_quote.current_price:.2f}")
            except Exception as e:
                logger.warning(f"[WebRAGService] Failed to retrieve live quote for {analysis.detected_ticker}: {e}")

        # Step 7: Construct Grounded Financial Prompt
        context_parts = []
        if live_quote:
            quote_text = (
                f"### Real-Time Market Quote for {live_quote.company_name} ({live_quote.ticker}):\n"
                f"- Price: {live_quote.currency} {live_quote.current_price:.2f} ({live_quote.change:+.2f} / {live_quote.change_percent:+.2f}%)\n"
                f"- Day Range: {live_quote.day_low} - {live_quote.day_high} | 52-Week Range: {live_quote.year_low} - {live_quote.year_high}\n"
                f"- P/E Ratio: {live_quote.pe_ratio or 'N/A'} | Market Cap: {live_quote.market_cap or 'N/A'}\n"
            )
            context_parts.append(quote_text)

        for p in selected_passages:
            context_parts.append(
                f"[Source {p.source.id}]: {p.source.title} ({p.source.url})\n{p.text}"
            )

        full_context = "\n\n---\n\n".join(context_parts)
        logger.debug(f"[WebRAGService] Final constructed prompt context length: {len(full_context):,} characters.")

        system_instruction = (
            "You are MarketMind AI, a senior institutional financial analyst and market intelligence assistant. "
            "Your role is to synthesize financial news, equity movements, and macroeconomic reports into clear, rigorous, "
            "objective insights.\n\n"
            "STRICT CITATION RULES:\n"
            "1. Every factual claim, number, date, or assertion MUST be supported by a citation tag corresponding "
            "to the source, e.g. [1], [2], or [1, 3].\n"
            "2. Never hallucinate numbers, prices, or percentages not provided in the context.\n"
            "3. If real-time market data is provided, highlight the current price and day change prominently.\n"
            "4. Organize your response with clear Markdown headings, bullet points for key takeaways, and a concise summary conclusion.\n"
            "5. Maintain an objective, institutional tone."
        )

        user_prompt = f"""Question: {request.query}

Context Information:
{full_context or "No detailed article text could be extracted. Use source snippets if available."}

Provide a comprehensive, well-structured financial analysis addressing the question with strict [X] source citations.
"""

        # Step 8: Stream Synthesis Tokens
        yield SSEMessage(event="status", data={"step": "generating", "message": "Synthesizing market response..."})
        logger.info(f"[WebRAGService] Initiating Gemini stream (temperature={settings.LLM_TEMPERATURE})...")

        token_count = 0
        try:
            async for token in self.llm.generate_stream(
                prompt=user_prompt,
                system_prompt=system_instruction,
                temperature=settings.LLM_TEMPERATURE
            ):
                token_count += 1
                yield SSEMessage(event="token", data={"token": token})
        except Exception as e:
            logger.error(f"[WebRAGService] Error streaming from Gemini: {e}")
            yield SSEMessage(event="error", data={"message": f"Generation error: {str(e)}"})
            return

        elapsed = round(time.time() - start_time, 2)
        logger.info(f"[WebRAGService] Generation finished: {token_count} tokens streamed in {elapsed}s.")
        yield SSEMessage(
            event="complete",
            data={"tokens_used": token_count, "duration_seconds": elapsed}
        )

    async def execute(
        self,
        request: RAGQueryRequest,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> RAGResult:
        """Non-streaming execution returning a consolidated RAGResult."""
        full_text = []
        sources = []
        tokens = 0
        duration = 0.0

        async for sse in self.stream(request, chat_history):
            if sse.event == "token":
                full_text.append(sse.data.get("token", ""))
            elif sse.event == "sources":
                raw_sources = sse.data.get("sources", [])
                sources = [SourceCitation(**s) for s in raw_sources]
            elif sse.event == "complete":
                tokens = sse.data.get("tokens_used", 0)
                duration = sse.data.get("duration_seconds", 0.0)

        return RAGResult(
            query=request.query,
            answer="".join(full_text),
            sources=sources,
            tokens_used=tokens,
            duration_seconds=duration
        )
