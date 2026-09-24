"""
Comprehensive Tests for LanceDB Semantic News Cache & Historical Document Vault.
"""

import os
import shutil
import tempfile
import pytest
from typing import List, Dict, Any, AsyncIterator

from app.domain.interfaces.llm import LLMClient
from app.domain.schemas.rag import (
    RAGQueryRequest,
    VaultQueryRequest,
    SourceCitation,
    ScrapedDocument,
)
from app.infrastructure.vector_store.lance_store import LanceVectorStore
from app.services.filings_vault import DocumentVaultService
from app.services.web_rag import WebRAGService


class DeterministicMockLLMClient:
    """Mock LLM client producing deterministic embeddings and streaming tokens."""

    async def get_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        # Produce a pseudo 768-dim unit vector
        embeddings = []
        for t in texts:
            val = float(len(t) % 10) / 10.0 + 0.1
            vec = [val] * 768
            embeddings.append(vec)
        return embeddings

    async def generate_stream(self, prompt: str, system_prompt: str = None, temperature: float = None) -> AsyncIterator[str]:
        yield "Institutional analysis: "
        yield "Tata Motors EV segment revenue grew 24% YoY."

    async def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = None) -> str:
        return "Tata Motors EV segment revenue grew 24% YoY with stable EBITDA margin."

    async def generate_structured(self, prompt: str, response_schema: Any, system_prompt: str = None) -> Any:
        from app.domain.schemas.rag import QueryAnalysisResult
        return QueryAnalysisResult(
            is_financial=True,
            detected_ticker="TATAMOTORS.NS",
            company_name="Tata Motors",
            requires_market_data=True,
            sub_queries=["Tata Motors Q3 FY25 financial results"]
        )


@pytest.fixture
def temp_lancedb_dir():
    """Provides an isolated temporary directory for LanceDB tests."""
    temp_dir = tempfile.mkdtemp(prefix="marketmind_lance_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_lance_news_cache_lifecycle(temp_lancedb_dir):
    """Verifies storing news, querying with freshness & ticker filters, and cache hits."""
    mock_llm = DeterministicMockLLMClient()
    store = LanceVectorStore(llm_client=mock_llm, db_uri=temp_lancedb_dir)

    passages = [
        {
            "text": "Tata Motors Q3 revenue rose 15% led by strong JLR sales in Europe and North America.",
            "url": "https://reuters.com/tata-q3",
            "title": "Tata Motors Q3 Earnings",
            "domain": "reuters.com",
            "snippet": "Strong JLR volumes drive Q3 earnings."
        },
        {
            "text": "Tata Motors commercial vehicle business maintained steady operating margins of 8.8%.",
            "url": "https://bloomberg.com/tata-cv",
            "title": "Tata CV Margins",
            "domain": "bloomberg.com",
            "snippet": "CV business holds margins."
        }
    ]

    # 1. Add passages to news cache
    count = await store.add_news_passages(passages=passages, ticker="TATAMOTORS.NS")
    assert count == 2

    # 2. Query cache with matching query & ticker
    results = await store.query_news_cache(
        query="Tata Motors Q3 revenue rose 15%",
        min_timestamp=0.0,
        ticker="TATAMOTORS.NS",
        top_k=5,
        max_distance=0.50
    )
    assert len(results) >= 1
    assert "Tata Motors" in results[0]["text"]
    assert results[0]["score"] > 0.5
    assert results[0]["ticker"] == "TATAMOTORS.NS"

    # 3. Query with distant past min_timestamp (should still match) vs future timestamp (should return empty)
    future_results = await store.query_news_cache(
        query="Tata Motors Q3 revenue",
        min_timestamp=9999999999.0,  # Far future
        ticker="TATAMOTORS.NS"
    )
    assert len(future_results) == 0


@pytest.mark.asyncio
async def test_lance_document_vault_lifecycle(temp_lancedb_dir):
    """Verifies indexing documents, multi-criteria filtering, listing, and deletion."""
    mock_llm = DeterministicMockLLMClient()
    store = LanceVectorStore(llm_client=mock_llm, db_uri=temp_lancedb_dir)
    vault = DocumentVaultService(llm_client=mock_llm, vector_store=store)

    sample_filing_content = (
        "Tata Motors Limited Annual Report FY2024. "
        "Consolidated revenue stood at INR 4,37,928 crores, expanding 26.6% year-on-year. "
        "Free cash flow generation remained robust at INR 26,900 crores, reducing net automotive debt to near-zero. "
        "Commercial vehicle EBITDA margins improved to 10.6% on richer product mix and cost discipline. "
        "Jaguar Land Rover achieved record EBIT margin of 8.5% driven by Defender and Range Rover deliveries."
    ).encode("utf-8")

    # 1. Index document
    doc_item = await vault.index_document(
        file_bytes=sample_filing_content,
        filename="Tata_Motors_Annual_Report_FY24.txt",
        ticker="TATAMOTORS.NS",
        title="Tata Motors FY24 Annual Report",
        doc_type="annual_report",
        fiscal_year=2024
    )

    assert doc_item.doc_id is not None
    assert doc_item.ticker == "TATAMOTORS.NS"
    assert doc_item.total_chunks >= 1
    assert doc_item.fiscal_year == 2024

    # 2. List documents
    all_docs = await vault.list_documents(ticker="TATAMOTORS.NS")
    assert len(all_docs) == 1
    assert all_docs[0].title == "Tata Motors FY24 Annual Report"

    # 3. Query passages with metadata filters
    passages = await vault.query_passages(
        query="What was the consolidated revenue and free cash flow?",
        ticker="TATAMOTORS.NS",
        fiscal_year=2024,
        doc_type="annual_report"
    )
    assert len(passages) >= 1
    assert "Consolidated revenue" in passages[0].text
    assert passages[0].fiscal_year == 2024
    assert passages[0].ticker == "TATAMOTORS.NS"

    # 4. Stream RAG query
    query_req = VaultQueryRequest(
        query="Summarize revenue growth and debt reduction",
        ticker="TATAMOTORS.NS",
        fiscal_year=2024
    )
    events = []
    async for sse in vault.stream_query(query_req):
        events.append(sse)

    event_types = [e.event for e in events]
    assert "status" in event_types
    assert "sources" in event_types
    assert "token" in event_types
    assert "complete" in event_types

    # 5. Delete document
    deleted = await vault.delete_document(doc_item.doc_id)
    assert deleted is True

    # 6. Verify list is now empty
    empty_docs = await vault.list_documents(ticker="TATAMOTORS.NS")
    assert len(empty_docs) == 0


@pytest.mark.asyncio
async def test_web_rag_semantic_cache_hit(temp_lancedb_dir):
    """Verifies that WebRAGService skips external search and yields cache_hit when LanceDB contains fresh news."""
    mock_llm = DeterministicMockLLMClient()
    store = LanceVectorStore(llm_client=mock_llm, db_uri=temp_lancedb_dir)

    # Pre-populate news cache with matching news
    passages = [
        {
            "text": "Tata Motors Q3 FY25 financial results: Net profit surged 28% to INR 7,025 crore on high JLR margins.",
            "url": "https://economictimes.com/tata-results",
            "title": "Tata Motors Q3 Results",
            "domain": "economictimes.com",
            "snippet": "Tata Motors Q3 Net profit jumped 28%."
        },
        {
            "text": "Operating cash flow for the quarter stood at INR 11,400 crore with debt reduction accelerating.",
            "url": "https://cnbc.com/tata-cashflow",
            "title": "Tata Motors Cash Flow",
            "domain": "cnbc.com",
            "snippet": "Operating cash flow strong."
        }
    ]
    await store.add_news_passages(passages=passages, ticker="TATAMOTORS.NS")

    # Setup WebRAGService with the pre-populated store
    service = WebRAGService(
        llm_client=mock_llm,
        vector_store=store
    )

    req = RAGQueryRequest(
        query="Tata Motors Q3 FY25 financial results",
        country="IN"
    )

    streamed_events = []
    async for msg in service.stream(req):
        streamed_events.append(msg)

    # Verify that cache_hit status was emitted
    status_steps = [e.data.get("step") for e in streamed_events if e.event == "status"]
    assert "cache_hit" in status_steps

    # Verify sources were emitted from cache
    sources_events = [e for e in streamed_events if e.event == "sources"]
    assert len(sources_events) == 1
    sources_data = sources_events[0].data["sources"]
    assert len(sources_data) >= 1
    assert "Tata Motors" in sources_data[0]["title"]


@pytest.mark.asyncio
async def test_vault_api_endpoints(temp_lancedb_dir):
    """Verifies FastAPI REST endpoints for the document vault."""
    import httpx
    from app.main import app
    from app.api.deps import get_document_vault_service

    mock_llm = DeterministicMockLLMClient()
    store = LanceVectorStore(llm_client=mock_llm, db_uri=temp_lancedb_dir)
    vault_service = DocumentVaultService(llm_client=mock_llm, vector_store=store)

    app.dependency_overrides[get_document_vault_service] = lambda: vault_service

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Upload a document
            file_data = b"Nvidia Q4 FY25 Report: Data center revenue rose to $35 billion driven by Blackwell architecture demand."
            upload_res = await client.post(
                "/api/v2/vault/upload",
                data={
                    "ticker": "NVDA",
                    "title": "Nvidia Q4 FY25 Earnings",
                    "doc_type": "10-Q",
                    "fiscal_year": 2025,
                    "quarter": "Q4"
                },
                files={"file": ("nvidia_q4.txt", file_data, "text/plain")}
            )
            assert upload_res.status_code == 200
            uploaded_doc = upload_res.json()
            assert uploaded_doc["ticker"] == "NVDA"
            assert uploaded_doc["total_chunks"] >= 1
            doc_id = uploaded_doc["doc_id"]

            # 2. List documents
            list_res = await client.get("/api/v2/vault/documents?ticker=NVDA")
            assert list_res.status_code == 200
            docs = list_res.json()
            assert len(docs) == 1
            assert docs[0]["title"] == "Nvidia Q4 FY25 Earnings"

            # 3. Query the vault (non-streaming JSON mode)
            query_res = await client.post(
                "/api/v2/vault/query?stream=false",
                json={
                    "query": "What was data center revenue?",
                    "ticker": "NVDA",
                    "fiscal_year": 2025
                }
            )
            assert query_res.status_code == 200
            ans_data = query_res.json()
            assert len(ans_data["passages"]) >= 1
            assert "Data center revenue" in ans_data["passages"][0]["text"]
            assert ans_data["passages"][0]["ticker"] == "NVDA"

            # 4. Delete document
            del_res = await client.delete(f"/api/v2/vault/documents/{doc_id}")
            assert del_res.status_code == 200
            assert del_res.json()["deleted"] is True

            # 5. Verify list is empty
            list_after = await client.get("/api/v2/vault/documents?ticker=NVDA")
            assert len(list_after.json()) == 0
    finally:
        app.dependency_overrides.clear()
