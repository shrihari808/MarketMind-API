"""
Historical Corporate Filings & Document Vault Endpoints for MarketMind API v2.
Provides REST and SSE endpoints for document ingestion, multi-filing semantic search,
and cross-document institutional RAG querying via LanceDB.
"""

import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db,
    get_client_id,
    get_document_vault_service,
)
from app.services.filings_vault import DocumentVaultService
from app.services.chat_history import ChatHistoryService
from app.domain.schemas.rag import (
    VaultDocumentItem,
    VaultQueryRequest,
    VaultPassageResult,
    VaultRAGResult,
)

router = APIRouter(prefix="/vault", tags=["Historical Document Vault (LanceDB)"])


@router.post(
    "/upload",
    response_model=VaultDocumentItem,
    summary="Index a Corporate Filing or Financial Document into the Vault"
)
async def upload_document_to_vault(
    file: UploadFile = File(..., description="PDF or text document (10-K, 10-Q, transcript, annual report)"),
    ticker: str = Form(..., description="Stock ticker symbol (e.g. TATAMOTORS.NS, NVDA, AAPL)"),
    title: str = Form(..., description="Document title (e.g. Tata Motors Q3 FY25 Earnings Release)"),
    doc_type: str = Form(default="general", description="10-K | 10-Q | annual_report | transcript | presentation | general"),
    fiscal_year: Optional[int] = Form(default=None, description="Fiscal year (e.g. 2024, 2025)"),
    quarter: Optional[str] = Form(default=None, description="Quarter if applicable (e.g. Q1, Q2, Q3, Q4)"),
    vault_service: DocumentVaultService = Depends(get_document_vault_service)
):
    """
    Ingests and vector-indexes a multi-page filing or earnings transcript into LanceDB.
    Chunks text with page numbers, generates 768-dim embeddings via Gemini, and registers metadata.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must have a valid filename.")

    # Read file bytes (enforce 30 MB limit for free tier safety)
    file_bytes = await file.read()
    if len(file_bytes) > 30 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 30MB limit."
        )

    try:
        item = await vault_service.index_document(
            file_bytes=file_bytes,
            filename=file.filename,
            ticker=ticker,
            title=title,
            doc_type=doc_type,
            fiscal_year=fiscal_year,
            quarter=quarter
        )
        return item
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to index document into vault: {str(e)}"
        )


@router.post(
    "/query",
    summary="Query Historical Filings Vault with SSE Streaming or JSON"
)
async def query_vault_endpoint(
    request: VaultQueryRequest,
    stream: bool = Query(default=True, description="Stream response tokens via Server-Sent Events (SSE)"),
    header_client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_db),
    vault_service: DocumentVaultService = Depends(get_document_vault_service)
):
    """
    Executes cross-document RAG across indexed filings in LanceDB.
    Supports filtering by ticker, document type, and fiscal year.
    Streams synthesized tokens using standardized SSE events:
    - `event: status` -> Step progress
    - `event: sources` -> Cited filing excerpts and page numbers
    - `event: token` -> Text chunks
    - `event: complete` -> Usage and latency
    - `event: error` -> Error details
    """
    client_id = request.client_id or header_client_id
    session_id = request.session_id or str(uuid.uuid4())
    request.client_id = client_id
    request.session_id = session_id

    if stream:
        async def event_generator():
            accumulated_tokens: List[str] = []
            async for sse_msg in vault_service.stream_query(request):
                if sse_msg.event == "token":
                    t = sse_msg.data.get("token", "")
                    accumulated_tokens.append(t)
                yield sse_msg.to_sse()

            # Save chat turns if session provided
            assistant_answer = "".join(accumulated_tokens)
            if assistant_answer and session_id:
                try:
                    from app.core.database import async_session_factory
                    async with async_session_factory() as save_db:
                        await ChatHistoryService.save_message(
                            db=save_db,
                            client_id=client_id,
                            session_id=session_id,
                            role="user",
                            content=f"[Vault Query: {request.ticker or 'All'}] {request.query}"
                        )
                        await ChatHistoryService.save_message(
                            db=save_db,
                            client_id=client_id,
                            session_id=session_id,
                            role="assistant",
                            content=assistant_answer
                        )
                except Exception:
                    pass

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        # Non-streaming fallback
        import time
        start_time = time.time()
        passages = await vault_service.query_passages(
            query=request.query,
            ticker=request.ticker,
            doc_type=request.doc_type,
            fiscal_year=request.fiscal_year,
            top_k=request.top_k
        )
        if not passages:
            return VaultRAGResult(
                query=request.query,
                answer="No relevant excerpts found in the historical filings vault.",
                passages=[],
                tokens_used=0,
                duration_seconds=round(time.time() - start_time, 2)
            )

        context_lines = [f"[{p.title} (Page {p.page_number})]: {p.text}" for p in passages]
        full_context = "\n\n".join(context_lines)
        prompt = f"Question: {request.query}\n\nExcerpts:\n{full_context}\n\nAnalyze and answer accurately."
        answer = await vault_service.llm.generate_text(prompt, system_prompt=vault_service.VAULT_SYSTEM_PROMPT)

        return VaultRAGResult(
            query=request.query,
            answer=answer,
            passages=passages,
            tokens_used=len(answer.split()),
            duration_seconds=round(time.time() - start_time, 2)
        )


@router.get(
    "/documents",
    response_model=List[VaultDocumentItem],
    summary="List Registered Documents in the Historical Filings Vault"
)
async def list_vault_documents(
    ticker: Optional[str] = Query(default=None, description="Filter documents by company ticker (e.g. TATAMOTORS.NS)"),
    vault_service: DocumentVaultService = Depends(get_document_vault_service)
):
    """Returns all registered corporate filings in LanceDB."""
    return await vault_service.list_documents(ticker=ticker)


@router.delete(
    "/documents/{doc_id}",
    summary="Delete a Document and its Vector Chunks from the Vault"
)
async def delete_vault_document(
    doc_id: str,
    vault_service: DocumentVaultService = Depends(get_document_vault_service)
):
    """Deletes an indexed document and removes its vector embeddings from LanceDB."""
    success = await vault_service.delete_document(doc_id=doc_id)
    return {"deleted": success, "doc_id": doc_id}


@router.delete(
    "/tickers/{ticker}",
    summary="Delete All Filings for a Ticker from the Vault"
)
async def delete_vault_ticker(
    ticker: str,
    vault_service: DocumentVaultService = Depends(get_document_vault_service)
):
    """Deletes all documents and vector embeddings for a specific stock ticker."""
    success = await vault_service.delete_ticker(ticker=ticker)
    return {"deleted": success, "ticker": ticker.upper()}
