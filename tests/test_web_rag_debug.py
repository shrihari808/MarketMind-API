"""
Unit and API tests for WebRAGService debug stage timings and retrieval_only mode.
"""

from typing import AsyncIterator, List, Optional, Type, TypeVar
import httpx
import pytest
from pydantic import BaseModel

from app.api.deps import get_web_rag_service
from app.domain.interfaces.llm import LLMClient
from app.domain.interfaces.market import MarketDataClient
from app.domain.interfaces.scraper import WebScraper
from app.domain.interfaces.search import SearchEngine
from app.domain.schemas.market import StockFundamentals, StockQuote
from app.domain.schemas.rag import QueryAnalysisResult, RAGQueryRequest, ScrapedDocument, SourceCitation
from app.main import app
from app.services.web_rag import WebRAGService

T = TypeVar("T", bound=BaseModel)


class StubLLMClient(LLMClient):
    def __init__(self, fail_stream: bool = False):
        self.fail_stream = fail_stream
        self.stream_called = False

    async def generate_stream(
        self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None
    ) -> AsyncIterator[str]:
        self.stream_called = True
        if self.fail_stream:
            raise RuntimeError("No API key")
        yield "Nvidia "
        yield "revenue grew [1]."

    async def generate_text(
        self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None
    ) -> str:
        return "Nvidia revenue grew."

    async def generate_structured(
        self, prompt: str, response_schema: Type[T], system_prompt: Optional[str] = None
    ) -> T:
        return response_schema.model_validate({
            "is_financial": True,
            "financial_reason": "Equity query",
            "detected_ticker": "NVDA",
            "company_name": "Nvidia",
            "requires_market_data": True,
            "sub_queries": ["Nvidia data center revenue", "Nvidia earnings outlook", "NVDA fundamentals"],
        })

    async def generate_multimodal_stream(
        self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf", system_prompt: Optional[str] = None
    ) -> AsyncIterator[str]:
        yield ""

    async def get_embeddings(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        return [[0.1] * 8 for _ in texts]


class StubSearchEngine(SearchEngine):
    async def search(
        self, query: str, max_results: int = 5, country: str = "IN", timelimit: Optional[str] = None
    ) -> List[SourceCitation]:
        return [
            SourceCitation(
                id=1,
                title="Nvidia Data Center Revenue Jumps",
                url="https://example.com/nvda-q3",
                snippet="Nvidia data center revenue surged in Q3.",
                publication_date="2026-11-10T10:00:00Z",
                domain="example.com",
            )
        ]

    async def search_news(
        self, query: str, max_results: int = 5, country: str = "IN", timelimit: Optional[str] = None
    ) -> List[SourceCitation]:
        return await self.search(query, max_results=max_results, country=country, timelimit=timelimit)


class StubScraper(WebScraper):
    async def scrape(self, url: str) -> ScrapedDocument:
        return ScrapedDocument(
            url=url,
            title="Nvidia Data Center Revenue Jumps",
            content="Nvidia reported record data center revenue driven by AI GPU demand and strong margin expansion.",
            published_date="2026-11-10",
            success=True,
        )

    async def scrape_many(self, urls: List[str]) -> List[ScrapedDocument]:
        return [await self.scrape(u) for u in urls]


class StubMarketClient(MarketDataClient):
    async def get_quote(self, ticker: str) -> Optional[StockQuote]:
        return StockQuote(
            ticker="NVDA",
            company_name="Nvidia",
            current_price=140.0,
            currency="USD",
            change=2.5,
            change_percent=1.8,
        )

    async def get_fundamentals(self, ticker: str) -> Optional[StockFundamentals]:
        return None

    async def resolve_ticker(self, query: str) -> Optional[str]:
        return "NVDA"

    async def get_quotes_batch(self, tickers: List[str]) -> List[StockQuote]:
        return []

    async def get_market_indices(self, country: str = "IN") -> List:
        return []

    async def get_top_movers(self, country: str = "IN") -> dict:
        return {"gainers": [], "losers": []}


@pytest.mark.asyncio
async def test_web_rag_retrieval_only_and_debug_timings():
    llm = StubLLMClient()
    svc = WebRAGService(
        llm_client=llm,
        search_engine=StubSearchEngine(),
        scraper=StubScraper(),
        market_client=StubMarketClient(),
        vector_store=None,
    )

    res = await svc.execute(
        RAGQueryRequest(query="Nvidia data center revenue", country="US"),
        debug=True,
        retrieval_only=True,
    )

    assert not llm.stream_called
    assert res.answer == ""
    assert len(res.sources) == 1
    assert res.stage_timings is not None
    assert res.stage_timings.retrieval_only is True
    assert res.stage_timings.retrieval_total_ms > 0
    assert res.stage_timings.candidates_found == 1
    assert res.stage_timings.urls_scraped == 1
    assert res.stage_timings.scrape_success_count == 1
    assert res.stage_timings.passages_selected == 1
    assert res.stage_timings.llm_total_ms is None
    assert res.selected_passages is not None and len(res.selected_passages) == 1


@pytest.mark.asyncio
async def test_web_rag_e2e_debug_timings():
    llm = StubLLMClient()
    svc = WebRAGService(
        llm_client=llm,
        search_engine=StubSearchEngine(),
        scraper=StubScraper(),
        market_client=StubMarketClient(),
        vector_store=None,
    )

    res = await svc.execute(
        RAGQueryRequest(query="Nvidia data center revenue", country="US"),
        debug=True,
        retrieval_only=False,
    )

    assert llm.stream_called
    assert "Nvidia revenue grew" in res.answer
    assert res.stage_timings is not None
    assert res.stage_timings.llm_ttft_ms is not None
    assert res.stage_timings.llm_total_ms is not None
    assert res.stage_timings.total_ms >= res.stage_timings.retrieval_total_ms


@pytest.mark.asyncio
async def test_web_rag_endpoint_debug_headers():
    svc = WebRAGService(
        llm_client=StubLLMClient(),
        search_engine=StubSearchEngine(),
        scraper=StubScraper(),
        market_client=StubMarketClient(),
        vector_store=None,
    )
    app.dependency_overrides[get_web_rag_service] = lambda: svc
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v2/rag/web?stream=false&debug=true&retrieval_only=true",
                json={"query": "Nvidia data center revenue", "country": "US"},
                headers={"X-Client-ID": "test-debug-client"},
            )
        assert resp.status_code == 200
        assert "X-RAG-Retrieval-Ms" in resp.headers
        assert "X-RAG-Total-Ms" in resp.headers
        data = resp.json()
        assert data["stage_timings"]["retrieval_only"] is True
        assert data["stage_timings"]["passages_selected"] == 1
    finally:
        app.dependency_overrides.clear()
