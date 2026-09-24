"""
Historical Corporate Filings & Document Vault Service.
Provides multi-document indexing, semantic chunking with page tracking,
metadata filtering, and institutional cross-document RAG synthesis using LanceDB.
"""

import time
import uuid
from io import BytesIO
from typing import AsyncIterator, List, Dict, Any, Optional
import pypdf

from app.core.config import get_settings
from app.core.logging import logger
from app.domain.interfaces.llm import LLMClient
from app.domain.schemas.rag import (
    VaultDocumentItem,
    VaultQueryRequest,
    VaultPassageResult,
    VaultRAGResult,
    SSEMessage,
)
from app.infrastructure.llm.gemini import GeminiLLMClient
from app.infrastructure.vector_store.lance_store import LanceVectorStore


class DocumentVaultService:
    """
    Service managing multi-document financial filings, earnings call transcripts,
    and annual reports archived in LanceDB Apache Arrow columnar storage.
    """

    VAULT_SYSTEM_PROMPT = (
        "You are an expert institutional equity research analyst and forensic financial auditor. "
        "You analyze historical corporate filings, annual reports (10-Ks), quarterly disclosures (10-Qs), "
        "and earnings conference call transcripts.\n\n"
        "Guidelines:\n"
        "1. Ground your analysis strictly on the provided filing excerpts.\n"
        "2. When multiple fiscal years or quarters are provided, explicitly compare year-over-year (YoY) "
        "or quarter-over-quarter (QoQ) metrics, margins, and operational performance.\n"
        "3. Accurately cite the specific document title, fiscal year, and page number for every critical statistic.\n"
        "4. Highlight management guidance adjustments, auditor risk factors, or accounting footnote disclosures.\n"
        "5. If information is not contained in the provided excerpts, clearly state that it is unavailable in the vault."
    )

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        vector_store: Optional[LanceVectorStore] = None
    ):
        self.llm = llm_client or GeminiLLMClient()
        self.vector_store = vector_store or LanceVectorStore(llm_client=self.llm)

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
        """Splits document text into word chunks with overlap."""
        words = text.split()
        if len(words) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunks.append(" ".join(words[start:end]))
            if end >= len(words):
                break
            start += chunk_size - overlap
        return chunks

    def _extract_text_and_pages(
        self,
        file_bytes: bytes,
        filename: str
    ) -> List[Dict[str, Any]]:
        """
        Extracts text content grouped by page number from PDF or raw text.
        Returns a list of dicts: [{"page_number": int, "text": str}]
        """
        pages_content: List[Dict[str, Any]] = []

        if filename.lower().endswith(".pdf"):
            try:
                reader = pypdf.PdfReader(BytesIO(file_bytes))
                logger.info(f"[DocumentVault] Read PDF '{filename}' with {len(reader.pages)} page(s).")
                for page_idx, page in enumerate(reader.pages, start=1):
                    extracted = page.extract_text() or ""
                    if extracted.strip():
                        pages_content.append({
                            "page_number": page_idx,
                            "text": extracted.strip()
                        })
            except Exception as e:
                logger.error(f"[DocumentVault] Failed to parse PDF with pypdf: {e}")
                raise ValueError(f"Could not read PDF file '{filename}': {str(e)}")
        else:
            # Plain text, markdown, or transcript
            try:
                raw_text = file_bytes.decode("utf-8", errors="replace").strip()
                if raw_text:
                    pages_content.append({"page_number": 1, "text": raw_text})
            except Exception as e:
                raise ValueError(f"Could not decode text file '{filename}': {str(e)}")

        return pages_content

    async def index_document(
        self,
        file_bytes: bytes,
        filename: str,
        ticker: str,
        title: str,
        doc_type: str = "general",
        fiscal_year: Optional[int] = None,
        quarter: Optional[str] = None
    ) -> VaultDocumentItem:
        """
        Extracts, chunks, embeds, and indexes a financial document into LanceDB.
        """
        doc_id = str(uuid.uuid4())
        clean_ticker = ticker.strip().upper()
        clean_title = title.strip() or filename
        clean_doc_type = doc_type.strip().lower()

        logger.info(
            f"[DocumentVault] Ingesting document '{clean_title}' for {clean_ticker} "
            f"({len(file_bytes):,} bytes, type={clean_doc_type}, FY={fiscal_year})..."
        )

        pages = self._extract_text_and_pages(file_bytes, filename)
        if not pages:
            raise ValueError(f"No readable text could be extracted from '{filename}'.")

        # Split into passage chunks
        chunks: List[Dict[str, Any]] = []
        for p in pages:
            page_text = p["text"]
            page_chunks = self._chunk_text(page_text, chunk_size=400, overlap=50)
            for chunk_str in page_chunks:
                if len(chunk_str.strip()) > 30:  # Skip tiny noise fragments
                    chunks.append({
                        "page_number": p["page_number"],
                        "text": chunk_str
                    })

        if not chunks:
            raise ValueError(f"No valid passages generated from document '{filename}'.")

        metadata = {
            "doc_id": doc_id,
            "ticker": clean_ticker,
            "title": clean_title,
            "doc_type": clean_doc_type,
            "fiscal_year": fiscal_year or 0,
            "quarter": quarter or "",
            "file_name": filename,
        }

        total_indexed = await self.vector_store.add_filing_chunks(chunks=chunks, metadata=metadata)

        item = VaultDocumentItem(
            doc_id=doc_id,
            ticker=clean_ticker,
            title=clean_title,
            doc_type=clean_doc_type,
            fiscal_year=fiscal_year,
            quarter=quarter,
            file_name=filename,
            total_chunks=total_indexed,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        logger.info(f"[DocumentVault] Document '{clean_title}' successfully indexed with {total_indexed} chunks.")
        return item

    async def query_passages(
        self,
        query: str,
        ticker: Optional[str] = None,
        doc_type: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        top_k: int = 6
    ) -> List[VaultPassageResult]:
        """
        Retrieves relevant filing chunks from LanceDB matching criteria.
        """
        raw_results = await self.vector_store.query_filings(
            query=query,
            ticker=ticker,
            doc_type=doc_type,
            fiscal_year=fiscal_year,
            top_k=top_k
        )

        passages = []
        for r in raw_results:
            passages.append(
                VaultPassageResult(
                    doc_id=r.get("doc_id", ""),
                    ticker=r.get("ticker", ""),
                    title=r.get("title", "Corporate Filing"),
                    doc_type=r.get("doc_type", "general"),
                    fiscal_year=r.get("fiscal_year") or None,
                    quarter=r.get("quarter") or None,
                    page_number=r.get("page_number") or 1,
                    text=r.get("text", ""),
                    score=r.get("score", 0.0)
                )
            )
        return passages

    async def stream_query(
        self,
        request: VaultQueryRequest
    ) -> AsyncIterator[SSEMessage]:
        """
        Executes cross-document RAG over the historical vault and yields SSE messages.
        """
        start_time = time.time()
        logger.info(
            f"[DocumentVault] Executing vault query: '{request.query}' "
            f"(ticker={request.ticker}, doc_type={request.doc_type}, FY={request.fiscal_year})"
        )

        filter_desc = []
        if request.ticker:
            filter_desc.append(f"ticker '{request.ticker}'")
        if request.fiscal_year:
            filter_desc.append(f"FY{request.fiscal_year}")
        if request.doc_type:
            filter_desc.append(f"type '{request.doc_type}'")

        filter_msg = f" for {', '.join(filter_desc)}" if filter_desc else ""
        yield SSEMessage(
            event="status",
            data={"step": "searching_vault", "message": f"Querying historical filings vault{filter_msg}..."}
        )

        passages = await self.query_passages(
            query=request.query,
            ticker=request.ticker,
            doc_type=request.doc_type,
            fiscal_year=request.fiscal_year,
            top_k=request.top_k
        )

        if not passages:
            yield SSEMessage(
                event="token",
                data={
                    "token": (
                        f"No relevant excerpts found in the historical filings vault matching your criteria "
                        f"(ticker={request.ticker or 'All'}, doc_type={request.doc_type or 'All'}, FY={request.fiscal_year or 'All'}).\n\n"
                        f"Please ensure documents have been uploaded to the vault via `/api/v2/vault/upload`."
                    )
                }
            )
            yield SSEMessage(
                event="complete",
                data={"tokens_used": 0, "duration_seconds": round(time.time() - start_time, 2)}
            )
            return

        # Emit citations to client
        sources_payload = [
            {
                "id": idx,
                "title": f"{p.title} (Page {p.page_number})",
                "ticker": p.ticker,
                "doc_type": p.doc_type,
                "fiscal_year": p.fiscal_year,
                "quarter": p.quarter,
                "score": p.score,
                "snippet": p.text[:220] + ("..." if len(p.text) > 220 else "")
            }
            for idx, p in enumerate(passages, start=1)
        ]
        yield SSEMessage(event="sources", data={"sources": sources_payload})

        # Step 2: Synthesis
        yield SSEMessage(
            event="status",
            data={"step": "synthesizing", "message": f"Analyzing {len(passages)} excerpts across indexed filings..."}
        )

        context_lines = []
        for idx, p in enumerate(passages, start=1):
            header = f"[Excerpt {idx}] Document: {p.title} | Ticker: {p.ticker}"
            if p.fiscal_year:
                header += f" | FY: {p.fiscal_year}"
            if p.quarter:
                header += f" | Quarter: {p.quarter}"
            header += f" | Page: {p.page_number}"

            context_lines.append(f"{header}\n{p.text}\n")

        full_context = "\n---\n".join(context_lines)

        user_prompt = (
            f"Question: {request.query}\n\n"
            f"### Verified Filing Excerpts from Historical Vault:\n"
            f"{full_context}\n\n"
            f"Provide an institutional-grade, multi-document synthesis addressing the question. "
            f"Compare fiscal periods if multiple years are present, and cite your findings."
        )

        token_count = 0
        try:
            async for token in self.llm.generate_stream(
                prompt=user_prompt,
                system_prompt=self.VAULT_SYSTEM_PROMPT
            ):
                token_count += 1
                yield SSEMessage(event="token", data={"token": token})
        except Exception as e:
            logger.error(f"[DocumentVault] Synthesis failed: {e}")
            yield SSEMessage(event="error", data={"message": f"Vault synthesis failed: {str(e)}"})
            return

        yield SSEMessage(
            event="complete",
            data={
                "tokens_used": token_count,
                "passages_used": len(passages),
                "duration_seconds": round(time.time() - start_time, 2)
            }
        )

    async def list_documents(self, ticker: Optional[str] = None) -> List[VaultDocumentItem]:
        """Lists registered documents in the vault."""
        raw_items = await self.vector_store.list_vault_documents(ticker=ticker)
        items = []
        for r in raw_items:
            items.append(
                VaultDocumentItem(
                    doc_id=r.get("doc_id", ""),
                    ticker=r.get("ticker", ""),
                    title=r.get("title", ""),
                    doc_type=r.get("doc_type", "general"),
                    fiscal_year=r.get("fiscal_year") or None,
                    quarter=r.get("quarter") or None,
                    file_name=r.get("file_name", ""),
                    total_chunks=r.get("total_chunks", 0),
                    created_at=r.get("created_at", "")
                )
            )
        return items

    async def delete_document(self, doc_id: str) -> bool:
        """Deletes a document from the vault."""
        return await self.vector_store.delete_vault_document(doc_id=doc_id)

    async def delete_ticker(self, ticker: str) -> bool:
        """Deletes all documents for a ticker from the vault."""
        return await self.vector_store.delete_vault_ticker(ticker=ticker)
