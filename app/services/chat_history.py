"""
Chat History Management Service.
Handles database persistence, session aggregation, and retrieval of multi-turn
chat history isolated by anonymous browser client UUID (client_id).
"""

import json
from typing import List, Optional, Dict
from sqlalchemy import select, delete, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import ChatMessageRecord
from app.core.logging import logger
from app.domain.schemas.rag import SourceCitation
from app.domain.schemas.chat import (
    ChatMessageItem,
    ChatSessionSummary,
    ChatSessionDetail,
)


class ChatHistoryService:
    """Service providing CRUD and context formatting for user-isolated chat history."""

    @staticmethod
    async def save_message(
        db: AsyncSession,
        client_id: str,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[List[SourceCitation]] = None,
        tokens: int = 0
    ) -> ChatMessageRecord:
        """Persists a new user or assistant message to the database."""
        sources_json = None
        if sources:
            sources_json = json.dumps([s.model_dump() for s in sources])

        record = ChatMessageRecord(
            client_id=client_id,
            session_id=session_id,
            role=role,
            content=content,
            sources_json=sources_json,
            tokens=tokens
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        logger.debug(f"[ChatHistory] Saved {role} message (id={record.id}) for client={client_id[:8]}..., session={session_id[:8]}...")
        return record

    @staticmethod
    async def list_sessions(
        db: AsyncSession,
        client_id: str,
        limit: int = 50
    ) -> List[ChatSessionSummary]:
        """
        Retrieves all chat sessions for a client_id, ordered by most recently active.
        """
        # Query distinct sessions with max created_at and count
        stmt = (
            select(
                ChatMessageRecord.session_id,
                func.count(ChatMessageRecord.id).label("msg_count"),
                func.min(ChatMessageRecord.created_at).label("created_at"),
                func.max(ChatMessageRecord.created_at).label("updated_at")
            )
            .where(ChatMessageRecord.client_id == client_id)
            .group_by(ChatMessageRecord.session_id)
            .order_by(desc("updated_at"))
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.all()

        summaries: List[ChatSessionSummary] = []
        for session_id, count, created_at, updated_at in rows:
            # Fetch the first user message for title
            first_user_stmt = (
                select(ChatMessageRecord.content)
                .where(
                    ChatMessageRecord.client_id == client_id,
                    ChatMessageRecord.session_id == session_id,
                    ChatMessageRecord.role == "user"
                )
                .order_by(ChatMessageRecord.created_at.asc())
                .limit(1)
            )
            first_user = (await db.execute(first_user_stmt)).scalar_one_or_none()
            title = first_user[:60] + ("..." if len(first_user or "") > 60 else "") if first_user else "Conversation"

            # Fetch the last message preview
            last_msg_stmt = (
                select(ChatMessageRecord.content)
                .where(
                    ChatMessageRecord.client_id == client_id,
                    ChatMessageRecord.session_id == session_id
                )
                .order_by(ChatMessageRecord.created_at.desc())
                .limit(1)
            )
            last_msg = (await db.execute(last_msg_stmt)).scalar_one_or_none() or ""
            preview = last_msg[:100] + ("..." if len(last_msg) > 100 else "")

            summaries.append(
                ChatSessionSummary(
                    session_id=session_id,
                    title=title,
                    last_message=preview,
                    message_count=count,
                    created_at=created_at.isoformat() if created_at else "",
                    updated_at=updated_at.isoformat() if updated_at else ""
                )
            )

        logger.info(f"[ChatHistory] Found {len(summaries)} session(s) for client={client_id[:8]}...")
        return summaries

    @staticmethod
    async def get_session_messages(
        db: AsyncSession,
        client_id: str,
        session_id: str
    ) -> List[ChatMessageItem]:
        """Fetches all messages in a session in chronological order."""
        stmt = (
            select(ChatMessageRecord)
            .where(
                ChatMessageRecord.client_id == client_id,
                ChatMessageRecord.session_id == session_id
            )
            .order_by(ChatMessageRecord.created_at.asc())
        )
        result = await db.execute(stmt)
        records = result.scalars().all()

        items: List[ChatMessageItem] = []
        for r in records:
            sources: List[SourceCitation] = []
            if r.sources_json:
                try:
                    raw = json.loads(r.sources_json)
                    sources = [SourceCitation.model_validate(s) for s in raw]
                except Exception:
                    pass

            items.append(
                ChatMessageItem(
                    id=r.id,
                    role=r.role,
                    content=r.content,
                    sources=sources,
                    tokens=r.tokens,
                    created_at=r.created_at.isoformat() if r.created_at else ""
                )
            )
        return items

    @staticmethod
    async def get_session_context(
        db: AsyncSession,
        client_id: str,
        session_id: str,
        limit: int = 6
    ) -> List[Dict[str, str]]:
        """
        Retrieves recent turns formatted as [{"role": "...", "content": "..."}]
        to feed into QueryAnalyzer for contextual multi-turn conversation.
        """
        stmt = (
            select(ChatMessageRecord.role, ChatMessageRecord.content)
            .where(
                ChatMessageRecord.client_id == client_id,
                ChatMessageRecord.session_id == session_id
            )
            .order_by(ChatMessageRecord.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.all()
        # Reverse to return chronological order
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    @staticmethod
    async def delete_session(
        db: AsyncSession,
        client_id: str,
        session_id: str
    ) -> bool:
        """Deletes all messages in a session for the specified client."""
        stmt = delete(ChatMessageRecord).where(
            ChatMessageRecord.client_id == client_id,
            ChatMessageRecord.session_id == session_id
        )
        result = await db.execute(stmt)
        await db.commit()
        deleted_count = result.rowcount
        logger.info(f"[ChatHistory] Deleted session={session_id[:8]}... ({deleted_count} messages removed)")
        return deleted_count > 0
