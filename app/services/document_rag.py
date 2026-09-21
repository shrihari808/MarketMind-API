"""
Gemini Native Multimodal Document RAG Service.
Performs zero-slicing, zero-OCR document analysis directly over raw PDF bytes
exploiting Gemini's native 1M+ token context window and visual document understanding.
"""

from typing import AsyncIterator, Optional
from app.core.logging import logger
from app.domain.interfaces.llm import LLMClient
from app.domain.schemas.rag import SSEMessage
from app.infrastructure.llm.gemini import GeminiLLMClient


class DocumentRAGService:
    """Document RAG service handling multi-page PDFs natively without disk deconstruction."""

    DOCUMENT_SYSTEM_PROMPT = (
        "You are an expert institutional financial document auditor and equity research analyst. "
        "You have direct multimodal access to the complete uploaded document (including visual charts, "
        "tabular financial statements, balance sheets, footnotes, and diagrams).\n\n"
        "Guidelines:\n"
        "1. Extract exact numbers, fiscal periods (e.g. Q3 FY25), and audited metrics directly from the text and tables.\n"
        "2. If charts or visual plots are present, describe their trends accurately with coordinate values where visible.\n"
        "3. Highlight significant risks, auditor qualifications, or non-GAAP adjustments where relevant.\n"
        "4. Organize your response with clear Markdown headings, bullet points, and clean Markdown tables.\n"
        "5. If information is not found in the document, explicitly state that it is omitted rather than speculating."
    )

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or GeminiLLMClient()

    async def stream_query(
        self,
        query: str,
        file_bytes: bytes,
        filename: str = "document.pdf",
        mime_type: str = "application/pdf"
    ) -> AsyncIterator[SSEMessage]:
        """
        Streams analysis for a user question directly from raw PDF bytes.
        """
        yield SSEMessage(
            event="status",
            data={"step": "processing_document", "message": f"Analyzing {filename} natively with Gemini..."}
        )

        user_prompt = (
            f"Please answer the following question thoroughly based on the provided document:\n\n"
            f"Question: {query}\n\n"
            f"Provide a structured, accurate analysis citing relevant sections or pages if identifiable."
        )

        token_count = 0
        try:
            async for token in self.llm.generate_multimodal_stream(
                prompt=user_prompt,
                file_bytes=file_bytes,
                mime_type=mime_type,
                system_prompt=self.DOCUMENT_SYSTEM_PROMPT
            ):
                token_count += 1
                yield SSEMessage(event="token", data={"token": token})
        except Exception as e:
            logger.error(f"Multimodal document analysis error for {filename}: {e}")
            yield SSEMessage(event="error", data={"message": f"Document processing failed: {str(e)}"})
            return

        yield SSEMessage(
            event="complete",
            data={"tokens_used": token_count, "filename": filename}
        )

    async def summarize_document(
        self,
        file_bytes: bytes,
        filename: str = "document.pdf",
        mime_type: str = "application/pdf"
    ) -> AsyncIterator[SSEMessage]:
        """
        Generates an executive summary of the document (key findings, financials, balance sheet highlights).
        """
        summary_query = (
            "Provide an executive financial summary of this document. Include:\n"
            "1. Core Purpose / Subject of the Document\n"
            "2. Key Financial Highlights & Operational Metrics (with table if applicable)\n"
            "3. Major Strategic Initiatives or Business Updates\n"
            "4. Key Risk Factors or Auditor Disclosures\n"
            "5. Forward-Looking Guidance or Conclusion"
        )
        async for msg in self.stream_query(
            query=summary_query,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type
        ):
            yield msg
