"""
Pydantic Schemas for Anonymous User Chat History and Session Management.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.domain.schemas.rag import SourceCitation


class ChatMessageItem(BaseModel):
    """Single chat turn in a session history."""
    id: int
    role: str = Field(..., description="'user' or 'assistant'")
    content: str
    sources: List[SourceCitation] = Field(default_factory=list)
    tokens: int = 0
    created_at: str


class ChatSessionSummary(BaseModel):
    """Metadata summary for a chat conversation session."""
    session_id: str
    title: str = Field(default="New Conversation", description="Generated title or first message preview")
    last_message: str = ""
    message_count: int = 0
    created_at: str
    updated_at: str


class ChatSessionDetail(BaseModel):
    """Detailed chat session history containing all turns."""
    session_id: str
    client_id: str
    messages: List[ChatMessageItem] = Field(default_factory=list)


class DeleteSessionResponse(BaseModel):
    """Response payload upon deleting a chat session."""
    session_id: str
    deleted: bool = True
    message: str = "Session deleted successfully."
