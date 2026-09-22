"""
Anonymous User-Wise Chat History Endpoints.
Enables instant conversation retrieval and management keyed by anonymous browser client UUID (client_id).
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_client_id
from app.services.chat_history import ChatHistoryService
from app.domain.schemas.chat import (
    ChatSessionSummary,
    ChatSessionDetail,
    DeleteSessionResponse,
)

router = APIRouter(prefix="/chat", tags=["Chat History"])


@router.get(
    "/sessions",
    response_model=List[ChatSessionSummary],
    summary="List all chat sessions for the client device"
)
async def list_sessions(
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_db)
) -> List[ChatSessionSummary]:
    """
    Retrieves all conversation sessions belonging to the current browser client UUID,
    ordered by most recently active.
    """
    return await ChatHistoryService.list_sessions(db, client_id=client_id)


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetail,
    summary="Get full conversation history for a session"
)
async def get_session(
    session_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_db)
) -> ChatSessionDetail:
    """
    Retrieves all chronological message turns (both user prompts and assistant answers)
    for a specific conversation session belonging to this client.
    """
    messages = await ChatHistoryService.get_session_messages(db, client_id=client_id, session_id=session_id)
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found for this client."
        )
    return ChatSessionDetail(
        session_id=session_id,
        client_id=client_id,
        messages=messages
    )


@router.delete(
    "/sessions/{session_id}",
    response_model=DeleteSessionResponse,
    summary="Delete a chat session"
)
async def delete_session(
    session_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_db)
) -> DeleteSessionResponse:
    """
    Deletes an entire chat session and its associated messages for the client.
    """
    deleted = await ChatHistoryService.delete_session(db, client_id=client_id, session_id=session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found or already deleted."
        )
    return DeleteSessionResponse(
        session_id=session_id,
        deleted=True,
        message=f"Session '{session_id}' and all message turns deleted successfully."
    )
