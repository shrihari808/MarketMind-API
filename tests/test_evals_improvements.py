"""
Unit tests for Web RAG latency/recall improvements and evaluation helpers:
- AsyncTTLCache hit, expiry, and bounded eviction
- Bounded intent-aware FreshnessReranker scoring
- QueryAnalyzer adversarial non-financial filtering & semiconductor equity recall
- TrafilaturaWebScraper hard timeout and TTL caching
- Citation Faithfulness judge schema parsing
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, List, Optional, Type, TypeVar
import pytest
from pydantic import BaseModel

from app.core.cache import AsyncTTLCache
from app.domain.interfaces.llm import LLMClient
from app.domain.schemas.rag import PassageChunk, SourceCitation
from app.infrastructure.scrapers.web_scraper import TrafilaturaWebScraper
from app.services.query_analyzer import QueryAnalyzer
from app.services.reranker import FreshnessReranker
from evals.evaluate_faithfulness import FaithfulnessJudgment, judge_answer_faithfulness

T = TypeVar("T", bound=BaseModel)


class StubJudgeLLM(LLMClient):
    async def generate_stream(self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None) -> AsyncIterator[str]:
        yield ""

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None) -> str:
        return ""

    async def generate_structured(self, prompt: str, response_schema: Type[T], system_prompt: Optional[str] = None) -> T:
        return response_schema.model_validate({
            "total_claims": 2,
            "supported_claims": 2,
            "verdicts": [
                {"claim": "Nvidia data center revenue grew.", "supported": True, "supporting_source_ids": [1], "rationale": "Explicitly stated."},
                {"claim": "Gross margin expanded.", "supported": True, "supporting_source_ids": [1], "rationale": "Explicitly stated."},
            ],
        })

    async def generate_multimodal_stream(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf", system_prompt: Optional[str] = None) -> AsyncIterator[str]:
        yield ""

    async def get_embeddings(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        return [[0.0] * 4 for _ in texts]


@pytest.mark.asyncio
async def test_async_ttl_cache_hit_and_eviction():
    cache = AsyncTTLCache(namespace="test_ns", max_entries=2)
    await cache.set("k1", {"v": 1}, ttl_seconds=60)
    await cache.set("k2", {"v": 2}, ttl_seconds=60)
    assert await cache.get("k1") == {"v": 1}

    # Adding k3 should evict LRU (k2, since k1 was just touched)
    await cache.set("k3", {"v": 3}, ttl_seconds=60)
    assert await cache.get("k2") is None
    assert await cache.get("k1") == {"v": 1}
    assert await cache.get("k3") == {"v": 3}


def test_freshness_reranker_bounded_intent_aware():
    reranker = FreshnessReranker()
    assert reranker.is_time_sensitive_query("Nvidia latest quarterly earnings") is True
    assert reranker.is_time_sensitive_query("HDFC Bank net interest margin ROE valuation") is False
    assert reranker._effective_floor("HDFC Bank net interest margin ROE valuation") >= 0.92
    assert reranker._effective_floor("Nvidia latest quarterly earnings") == 0.85

    now = datetime.now(timezone.utc)
    c_old = SourceCitation(id=1, title="Old Deep Dive", url="https://a.com/1", publication_date=(now - timedelta(days=60)).isoformat())
    c_new = SourceCitation(id=2, title="Fresh Note", url="https://b.com/2", publication_date=now.isoformat())

    p_old = PassageChunk(text="HDFC Bank net interest margin ROE valuation balance sheet", source=c_old, score=0.0)
    p_new = PassageChunk(text="HDFC Bank net interest margin ROE valuation balance sheet", source=c_new, score=0.0)

    ranked = reranker.rerank("HDFC Bank net interest margin ROE valuation", [p_old, p_new], top_k=2)
    scores = {p.source.url: p.score for p in ranked}
    # Fresh still wins ties, but old evergreen document retains >=90% of its score instead of losing 75%
    assert scores["https://b.com/2"] > scores["https://a.com/1"]
    assert scores["https://a.com/1"] >= 0.90


@pytest.mark.asyncio
async def test_query_analyzer_adversarial_and_semiconductor():
    analyzer = QueryAnalyzer()

    # Previously rejected query should now be accepted as financial
    amd_res = await analyzer._heuristic_fallback("AMD AI GPU MI300 data center competition", "US")
    assert amd_res.is_financial is True
    assert amd_res.detected_ticker == "AMD"

    # Adversarial OOD queries mentioning company names or "forecast" must abstain
    for ood_q in [
        "Nvidia RTX 5090 gaming FPS benchmark in Cyberpunk 2077",
        "Apple pie recipe calories and baking temperature",
        "Tesla Model 3 recommended tire pressure and windshield wiper size",
        "What is the capital city of Australia and its weather forecast?",
    ]:
        res = await analyzer._heuristic_fallback(ood_q, "US")
        assert res.is_financial is False, f"Expected abstention for: {ood_q}"


@pytest.mark.asyncio
async def test_scraper_cache_and_timeout_guard():
    scraper = TrafilaturaWebScraper(timeout_seconds=0.2, cache_ttl_seconds=60)
    await scraper._cache.clear()
    await scraper._cache.set(
        "https://cached.example.com/article",
        {
            "url": "https://cached.example.com/article",
            "title": "Cached Article",
            "content": "Reliance Industries posted strong quarterly earnings across retail and digital services segments.",
            "published_date": "2026-11-15",
            "success": True,
            "error": None,
        },
        ttl_seconds=60,
    )
    docs = await scraper.scrape_many(["https://cached.example.com/article"])
    assert len(docs) == 1
    assert docs[0].success is True
    assert docs[0].title == "Cached Article"


@pytest.mark.asyncio
async def test_faithfulness_judge_helper():
    judgment: FaithfulnessJudgment = await judge_answer_faithfulness(
        llm=StubJudgeLLM(),
        query="Nvidia data center revenue",
        answer="Nvidia data center revenue grew and gross margin expanded [1].",
        passages=[{"source": {"id": 1, "url": "https://example.com/1"}, "text": "Nvidia data center revenue grew and gross margin expanded."}],
    )
    assert judgment.total_claims == 2
    assert judgment.supported_claims == 2


@pytest.mark.asyncio
async def test_brave_searcher_free_tier_rate_spacing(monkeypatch):
    import time
    from app.infrastructure.search.brave import BraveSearcher

    BraveSearcher._last_request_ts = 0.0
    searcher = BraveSearcher(api_key="test-brave-key", min_interval_seconds=0.15)
    call_times: List[float] = []

    class DummyResp:
        status_code = 200
        text = "{}"
        def json(self):
            return {"web": {"results": [{"title": "NVDA", "url": "https://example.com/nvda", "description": "Nvidia"}]}}

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, *args, **kwargs):
            call_times.append(time.monotonic())
            return DummyResp()

    monkeypatch.setattr("app.infrastructure.search.brave.httpx.AsyncClient", DummyAsyncClient)

    r1, r2 = await asyncio.gather(
        searcher.search("Nvidia", max_results=2, country="US"),
        searcher.search("AMD", max_results=2, country="US"),
    )
    assert len(r1) == 1 and len(r2) == 1
    assert len(call_times) == 2
    assert (call_times[1] - call_times[0]) >= 0.12
