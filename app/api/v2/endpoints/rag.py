"""
Standardized Server-Sent Events (SSE) RAG Endpoints for MarketMind API v2.
Includes Web RAG streaming, Multimodal PDF analysis, and Reddit sentiment discovery.
"""

import uuid
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db,
    get_client_id,
    get_web_rag_service,
    get_document_rag_service,
    get_reddit_rag_service,
)
from app.services.web_rag import WebRAGService
from app.services.document_rag import DocumentRAGService
from app.services.reddit_rag import RedditRAGService
from app.services.chat_history import ChatHistoryService
from app.domain.schemas.rag import (
    RAGQueryRequest,
    RAGResult,
    CommunitySentimentResult,
    SourceCitation,
)

router = APIRouter(prefix="/rag", tags=["RAG & Intelligence"])


@router.post(
    "/web",
    summary="Financial Web RAG with Real-time Quotes and SSE Streaming"
)
async def web_rag_endpoint(
    request: RAGQueryRequest,
    stream: bool = Query(default=True, description="Stream response tokens via Server-Sent Events (SSE)"),
    header_client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_db),
    rag_service: WebRAGService = Depends(get_web_rag_service)
):
    """
    Executes grounded financial search across news and web sources, reranks with BM25,
    injects real-time market data, and streams synthesized tokens using standardized SSE events:
    - `event: status` -> Step progress updates
    - `event: sources` -> Cited articles metadata
    - `event: token` -> Text chunks
    - `event: complete` -> Usage and duration
    - `event: error` -> Error messages
    """
    # Resolve client_id and session_id
    client_id = request.client_id or header_client_id
    session_id = request.session_id or str(uuid.uuid4())
    request.client_id = client_id
    request.session_id = session_id

    # Retrieve prior conversation turns if this is a continuing session
    chat_history = await ChatHistoryService.get_session_context(db, client_id=client_id, session_id=session_id)

    if stream:
        async def event_generator():
            accumulated_tokens: List[str] = []
            captured_sources: List[SourceCitation] = []
            token_count = 0

            # Stream from service
            async for sse_msg in rag_service.stream(request, chat_history=chat_history):
                if sse_msg.event == "token":
                    t = sse_msg.data.get("token", "")
                    accumulated_tokens.append(t)
                elif sse_msg.event == "sources":
                    raw_sources = sse_msg.data.get("sources", [])
                    captured_sources = [SourceCitation.model_validate(s) for s in raw_sources]
                elif sse_msg.event == "complete":
                    token_count = sse_msg.data.get("tokens_used", 0)

                yield sse_msg.to_sse()

            # Automatically persist conversation turns for this anonymous client
            assistant_answer = "".join(accumulated_tokens)
            if assistant_answer:
                try:
                    from app.core.database import async_session_factory
                    async with async_session_factory() as save_db:
                        await ChatHistoryService.save_message(
                            db=save_db,
                            client_id=client_id,
                            session_id=session_id,
                            role="user",
                            content=request.query
                        )
                        await ChatHistoryService.save_message(
                            db=save_db,
                            client_id=client_id,
                            session_id=session_id,
                            role="assistant",
                            content=assistant_answer,
                            sources=captured_sources,
                            tokens=token_count
                        )
                except Exception:
                    pass

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Session-ID": session_id
            }
        )

    # Non-streaming execution
    result = await rag_service.execute(request, chat_history=chat_history)
    try:
        await ChatHistoryService.save_message(
            db=db, client_id=client_id, session_id=session_id, role="user", content=request.query
        )
        await ChatHistoryService.save_message(
            db=db, client_id=client_id, session_id=session_id, role="assistant",
            content=result.answer, sources=result.sources, tokens=result.tokens_used
        )
    except Exception:
        pass

    return result


@router.post(
    "/document",
    summary="Multimodal PDF Financial Document Q&A via SSE Streaming"
)
async def document_rag_endpoint(
    file: UploadFile = File(..., description="Financial report or filing (PDF format)"),
    query: str = Form(..., description="User question regarding the uploaded document"),
    doc_service: DocumentRAGService = Depends(get_document_rag_service)
):
    """
    Streams multimodal document analysis directly from raw PDF bytes using Gemini's native
    1M+ token window. No OCR, chunking, or disk storage required.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF documents are supported."
        )

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:  # 20MB limit
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 20 MB limit."
        )

    async def event_generator():
        async for sse_msg in doc_service.stream_query(
            query=query,
            file_bytes=file_bytes,
            filename=file.filename or "document.pdf",
            mime_type=file.content_type or "application/pdf"
        ):
            yield sse_msg.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post(
    "/document/summary",
    summary="Multimodal Executive Financial Summary of PDF via SSE Streaming"
)
async def document_summary_endpoint(
    file: UploadFile = File(..., description="Financial statement or annual report (PDF format)"),
    doc_service: DocumentRAGService = Depends(get_document_rag_service)
):
    """
    Streams an institutional executive summary (key highlights, financials, risk factors)
    directly from an uploaded PDF.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF documents are supported."
        )

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 20 MB limit."
        )

    async def event_generator():
        async for sse_msg in doc_service.stream_summary(
            file_bytes=file_bytes,
            filename=file.filename or "document.pdf"
        ):
            yield sse_msg.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


class RedditSentimentRequest(BaseModel):
    """Optional JSON payload for Reddit sentiment analysis."""
    topic: Optional[str] = Field(None, description="Target company or stock/crypto topic")
    country: Optional[str] = Field(default="IN", description="Country context (e.g. 'IN', 'US')")


@router.post(
    "/reddit",
    response_model=CommunitySentimentResult,
    summary="Reddit Financial Community Sentiment Analysis"
)
async def reddit_sentiment_endpoint(
    request: Optional[RedditSentimentRequest] = None,
    topic: Optional[str] = Query(None, description="Ticker or stock/crypto topic (e.g. 'Reliance', 'NVDA')"),
    country: Optional[str] = Query(None, description="Country context (e.g. 'IN', 'US')"),
    reddit_service: RedditRAGService = Depends(get_reddit_rag_service)
) -> CommunitySentimentResult:
    """
    Searches retail investor communities on Reddit (e.g. r/IndianStockMarket, r/wallstreetbets)
    without paid Reddit API keys, aggregates discussion threads, and synthesizes structured
    consensus sentiment (Bullish vs. Bearish arguments, normalized sentiment score).
    Accepts input via JSON body or query parameters.
    """
    resolved_topic = (request.topic if request and request.topic else topic)
    if not resolved_topic or len(resolved_topic.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'topic' is required with at least 2 characters."
        )

    resolved_country = (request.country if request and request.country else country) or "IN"
    return await reddit_service.analyze_sentiment(
        topic=resolved_topic.strip(),
        country=resolved_country.strip()
    )
