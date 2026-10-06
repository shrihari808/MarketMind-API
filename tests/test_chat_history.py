"""
Unit & Integration Tests for Anonymous Client Chat History Persistence.
Tests message saving, session listing, context formatting, client isolation, and session deletion.
"""

import pytest
from app.core.database import async_session_factory
from app.domain.schemas.rag import SourceCitation
from app.services.chat_history import ChatHistoryService


@pytest.mark.asyncio
async def test_chat_history_lifecycle():
    client_id = "test_client_alpha"
    session_id = "sess_001"

    async with async_session_factory() as db:
        # 1. Save user turn
        user_msg = await ChatHistoryService.save_message(
            db=db,
            client_id=client_id,
            session_id=session_id,
            role="user",
            content="What are the profit margins for Apple?"
        )
        assert user_msg.id is not None
        assert user_msg.role == "user"

        # 2. Save assistant turn with citations and tokens
        citations = [
            SourceCitation(id=1, title="Apple 10-K", url="https://sec.gov/aapl", snippet="Gross margin 46.2%")
        ]
        asst_msg = await ChatHistoryService.save_message(
            db=db,
            client_id=client_id,
            session_id=session_id,
            role="assistant",
            content="Apple reported a gross margin of 46.2%.",
            sources=citations,
            tokens=45
        )
        assert asst_msg.id is not None
        assert asst_msg.tokens == 45

        # 3. Retrieve session messages
        messages = await ChatHistoryService.get_session_messages(db, client_id=client_id, session_id=session_id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert len(messages[1].sources) == 1
        assert messages[1].sources[0].title == "Apple 10-K"

        # 4. Context for LLM prompt formatting
        context = await ChatHistoryService.get_session_context(db, client_id=client_id, session_id=session_id)
        assert len(context) == 2
        assert context[0] == {"role": "user", "content": "What are the profit margins for Apple?"}
        assert context[1] == {"role": "assistant", "content": "Apple reported a gross margin of 46.2%."}

        # 5. List sessions
        sessions = await ChatHistoryService.list_sessions(db, client_id=client_id)
        assert len(sessions) >= 1
        matched = next((s for s in sessions if s.session_id == session_id), None)
        assert matched is not None
        assert matched.message_count == 2
        assert "What are the profit margins for Apple?" in matched.title

        # 6. Delete session
        deleted = await ChatHistoryService.delete_session(db, client_id=client_id, session_id=session_id)
        assert deleted is True

        # Verify messages deleted
        after_messages = await ChatHistoryService.get_session_messages(db, client_id=client_id, session_id=session_id)
        assert len(after_messages) == 0


@pytest.mark.asyncio
async def test_client_id_session_isolation():
    client_a = "client_isolated_A"
    client_b = "client_isolated_B"
    shared_session_name = "session_xyz"

    async with async_session_factory() as db:
        try:
            # Client A writes to session_xyz
            await ChatHistoryService.save_message(
                db=db,
                client_id=client_a,
                session_id=shared_session_name,
                role="user",
                content="Message from Client A"
            )

            # Client B writes to session_xyz
            await ChatHistoryService.save_message(
                db=db,
                client_id=client_b,
                session_id=shared_session_name,
                role="user",
                content="Message from Client B"
            )

            # Client A should only see Client A's message
            msgs_a = await ChatHistoryService.get_session_messages(db, client_id=client_a, session_id=shared_session_name)
            assert len(msgs_a) == 1
            assert msgs_a[0].content == "Message from Client A"

            # Client B should only see Client B's message
            msgs_b = await ChatHistoryService.get_session_messages(db, client_id=client_b, session_id=shared_session_name)
            assert len(msgs_b) == 1
            assert msgs_b[0].content == "Message from Client B"
        finally:
            await ChatHistoryService.delete_session(db, client_id=client_a, session_id=shared_session_name)
            await ChatHistoryService.delete_session(db, client_id=client_b, session_id=shared_session_name)
