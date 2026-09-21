"""
Pydantic Schemas for Retrieval-Augmented Generation (RAG) Pipelines.
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    """Incoming user query request for RAG."""
    query: str = Field(..., min_length=2, max_length=1000, description="The user's search or financial question")
    session_id: Optional[str] = Field(default=None, description="Client session ID for conversation memory")
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
