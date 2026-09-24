"""
Pydantic Schemas for Retrieval-Augmented Generation (RAG) Pipelines.
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    """Incoming user query request for RAG."""
    query: str = Field(..., min_length=2, max_length=1000, description="The user's search or financial question")
    session_id: Optional[str] = Field(default=None, description="Client session ID for conversation memory")
    client_id: Optional[str] = Field(default=None, description="Anonymous client browser UUID for user-isolated history")
    country: str = Field(default="IN", description="ISO 2-letter country code (e.g. IN, US)")


class SourceCitation(BaseModel):
    """Metadata for a cited external source."""
    id: int = Field(..., description="Citation index (1, 2, ...)")
    title: str = Field(..., description="Title of the article or webpage")
    url: str = Field(..., description="Full source URL")
    snippet: Optional[str] = Field(default=None, description="Extracted snippet or summary")
    publication_date: Optional[str] = Field(default=None, description="Publication date if available")
    domain: Optional[str] = Field(default=None, description="Base domain name (e.g. moneycontrol.com)")


class ScrapedDocument(BaseModel):
    """Result of scraping an article or web page."""
    url: str
    title: str = ""
    content: str = ""
    published_date: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


class RAGResult(BaseModel):
    """Final non-streaming RAG output object."""
    query: str
    answer: str
    sources: List[SourceCitation] = []
    tokens_used: int = 0
    duration_seconds: float = 0.0


class SSEMessage(BaseModel):
    """Standardized Server-Sent Events (SSE) packet format."""
    event: Literal["status", "sources", "token", "error", "complete"]
    data: Dict[str, Any]

    def to_sse(self) -> str:
        """Formats the object into the official SSE line protocol."""
        import json
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


class QueryAnalysisResult(BaseModel):
    """Output of the financial query analyzer."""
    is_financial: bool = Field(default=True, description="Whether query relates to finance, stocks, economy, or business")
    financial_reason: Optional[str] = Field(default=None, description="Explanation for classification")
    detected_ticker: Optional[str] = Field(default=None, description="Resolved ticker symbol if found (e.g. RELIANCE.NS, AAPL)")
    company_name: Optional[str] = Field(default=None, description="Extracted company name if present")
    requires_market_data: bool = Field(default=False, description="True if real-time price or fundamentals are needed")
    sub_queries: List[str] = Field(default_factory=list, description="Targeted sub-queries for multi-angle retrieval")
    target_date: Optional[str] = Field(default=None, description="Extracted date or time constraint if specified")
    reformulated_query: Optional[str] = Field(default=None, description="Context-enriched query if it was a follow-up")


class PassageChunk(BaseModel):
    """Segmented passage extracted from a scraped document with citation linkage."""
    text: str
    source: SourceCitation
    score: float = 0.0
    chunk_index: int = 0


class CommunitySentimentResult(BaseModel):
    """Synthesized sentiment report from retail community discussions."""
    topic: str
    overall_sentiment: str = Field(default="Neutral", description="Bullish | Bearish | Neutral | Mixed")
    sentiment_score: float = Field(default=0.0, description="Normalized score from -1.0 (very bearish) to +1.0 (very bullish)")
    summary: str = Field(default="", description="Executive narrative summary of community consensus")
    bullish_arguments: List[str] = Field(default_factory=list, description="Top positive points raised by community")
    bearish_arguments: List[str] = Field(default_factory=list, description="Top negative or risk points raised by community")
    top_discussions: List[SourceCitation] = Field(default_factory=list, description="Cited Reddit discussions or threads")


class DeepResearchResult(BaseModel):
    """Comprehensive institutional-grade equity research report."""
    ticker: str
    company_name: str
    executive_summary: str = ""
    markdown_report: str = ""
    recommendation: Optional[str] = Field(default=None, description="Analyst consensus or stance")
    sources: List[SourceCitation] = Field(default_factory=list)
    created_at: str = Field(default="")
    pdf_available: bool = False


class VaultDocumentItem(BaseModel):
    """Metadata of an indexed historical filing or document in the vault."""
    doc_id: str = Field(..., description="Unique document identifier")
    ticker: str = Field(..., description="Associated company ticker symbol")
    title: str = Field(..., description="Document title or description")
    doc_type: str = Field(default="general", description="10-K | 10-Q | annual_report | transcript | presentation | general")
    fiscal_year: Optional[int] = Field(default=None, description="Fiscal year (e.g. 2024)")
    quarter: Optional[str] = Field(default=None, description="Quarter if applicable (e.g. Q1, Q2, Q3, Q4)")
    file_name: str = Field(default="", description="Original file name")
    total_chunks: int = Field(default=0, description="Number of indexed passage vectors")
    created_at: str = Field(default="", description="ISO timestamp of indexing")


class VaultQueryRequest(BaseModel):
    """Query request for historical filings vault."""
    query: str = Field(..., min_length=2, max_length=1000, description="Financial research or filing question")
    ticker: Optional[str] = Field(default=None, description="Filter by company ticker (e.g. TATAMOTORS.NS, NVDA)")
    doc_type: Optional[str] = Field(default=None, description="Filter by document type (e.g. 10-K, 10-Q, annual_report, transcript)")
    fiscal_year: Optional[int] = Field(default=None, description="Filter by fiscal year (e.g. 2024)")
    top_k: int = Field(default=6, description="Number of passage chunks to retrieve")
    session_id: Optional[str] = Field(default=None)
    client_id: Optional[str] = Field(default=None)


class VaultPassageResult(BaseModel):
    """Passage chunk retrieved from the filings vault."""
    doc_id: str
    ticker: str
    title: str
    doc_type: str
    fiscal_year: Optional[int] = None
    quarter: Optional[str] = None
    page_number: Optional[int] = None
    text: str
    score: float = 0.0


class VaultRAGResult(BaseModel):
    """Non-streaming response from the historical document vault."""
    query: str
    answer: str
    passages: List[VaultPassageResult] = []
    tokens_used: int = 0
    duration_seconds: float = 0.0
