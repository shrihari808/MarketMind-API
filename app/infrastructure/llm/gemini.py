"""
Google Gemini AI Engine Adapter.
Implements the LLMClient protocol using Google's official Generative AI SDK with streaming,
Pydantic structured output, and native multimodal document analysis.
"""

import asyncio
from typing import AsyncIterator, Optional, Type, TypeVar, List
from pydantic import BaseModel
import google.generativeai as genai
from app.core.config import get_settings
from app.core.logging import logger
from app.domain.interfaces.llm import LLMClient

T = TypeVar("T", bound=BaseModel)


class GeminiLLMClient(LLMClient):
    """Concrete Google Gemini AI adapter."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self.embedding_model_name = settings.GEMINI_EMBEDDING_MODEL

        if self.api_key:
            genai.configure(api_key=self.api_key)
            logger.info(f"Gemini client initialized with model: {self.model_name}")
        else:
            logger.warning("GEMINI_API_KEY not configured. Set it in .env to enable Gemini features.")

    def _ensure_configured(self):
        if not self.api_key:
            # Re-check settings in case it was set dynamically
            settings = get_settings()
            if settings.GEMINI_API_KEY:
                self.api_key = settings.GEMINI_API_KEY
                genai.configure(api_key=self.api_key)
            else:
                raise ValueError("GEMINI_API_KEY is required but not configured.")

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> AsyncIterator[str]:
        """Streams generated tokens asynchronously."""
        self._ensure_configured()
        settings = get_settings()
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        logger.debug(f"[GeminiLLMClient] Initiating stream with model={self.model_name}, temp={temp}, prompt_len={len(prompt)}")
        
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(temperature=temp)
        )

        def _sync_stream():
            return model.generate_content(prompt, stream=True)

        response = await asyncio.to_thread(_sync_stream)
        token_count = 0
        for chunk in response:
            if chunk.text:
                token_count += 1
                yield chunk.text
                await asyncio.sleep(0)  # Yield control to event loop

        logger.debug(f"[GeminiLLMClient] Stream completed. Yielded {token_count} chunks.")

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generates a complete textual response."""
        self._ensure_configured()
        settings = get_settings()
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        logger.debug(f"[GeminiLLMClient] Generating text with model={self.model_name}, temp={temp}, prompt_len={len(prompt)}")

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(temperature=temp)
        )

        response = await asyncio.to_thread(model.generate_content, prompt)
        text_out = response.text if response and response.text else ""
        logger.debug(f"[GeminiLLMClient] Generated {len(text_out)} chars of text response.")
        return text_out

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_prompt: Optional[str] = None
    ) -> T:
        """Generates a structured output adhering strictly to the provided Pydantic model."""
        self._ensure_configured()
        logger.debug(f"[GeminiLLMClient] Generating structured output for schema: {response_schema.__name__}")

        # Instruct Gemini to output pure JSON matching schema
        schema_json = response_schema.model_json_schema()
        instructions = (
            f"{system_prompt or ''}\n\n"
            f"You MUST respond ONLY with valid JSON strictly conforming to this schema:\n"
            f"{schema_json}"
        )

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=instructions,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )

        response = await asyncio.to_thread(model.generate_content, prompt)
        logger.debug(f"[GeminiLLMClient] Received structured JSON ({len(response.text)} chars). Validating schema...")
        return response_schema.model_validate_json(response.text)

    async def generate_multimodal_stream(
        self,
        prompt: str,
        file_bytes: bytes,
        mime_type: str = "application/pdf",
        system_prompt: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Streams analysis directly from a multimodal file (e.g. PDF) exploiting Gemini's
        native 1M+ token context window.
        """
        self._ensure_configured()
        logger.info(f"[GeminiLLMClient] Starting multimodal stream for {len(file_bytes):,} bytes ({mime_type})")

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_prompt
        )

        part = {
            "mime_type": mime_type,
            "data": file_bytes
        }

        def _sync_stream():
            return model.generate_content([part, prompt], stream=True)

        response = await asyncio.to_thread(_sync_stream)
        chunk_count = 0
        for chunk in response:
            if chunk.text:
                chunk_count += 1
                yield chunk.text
                await asyncio.sleep(0)
        logger.info(f"[GeminiLLMClient] Multimodal stream completed ({chunk_count} chunks generated).")

    async def get_embeddings(
        self,
        texts: List[str],
        batch_size: Optional[int] = None
    ) -> List[List[float]]:
        """
        Generates embeddings using Gemini text-embedding-004 with configurable batching.
        """
        self._ensure_configured()
        if not texts:
            return []

        settings = get_settings()
        effective_batch_size = max(1, batch_size or settings.EMBEDDING_BATCH_SIZE)
        total_texts = len(texts)
        total_batches = (total_texts + effective_batch_size - 1) // effective_batch_size
        logger.info(
            f"[GeminiLLMClient] Generating embeddings for {total_texts} texts "
            f"across {total_batches} batch(es) (batch_size={effective_batch_size})."
        )

        all_embeddings: List[List[float]] = []

        for b_idx in range(0, total_texts, effective_batch_size):
            batch = texts[b_idx:b_idx + effective_batch_size]
            logger.debug(f"[GeminiLLMClient] Embedding batch {b_idx // effective_batch_size + 1}/{total_batches} ({len(batch)} texts)...")

            def _embed_batch(batch_slice):
                result = genai.embed_content(
                    model=self.embedding_model_name,
                    content=batch_slice,
                    task_type="retrieval_document"
                )
                return result.get("embedding", [])

            batch_embs = await asyncio.to_thread(_embed_batch, batch)

            # Handle single vs batch format returned by SDK
            if len(batch) == 1 and isinstance(batch_embs, list) and len(batch_embs) > 0 and isinstance(batch_embs[0], float):
                all_embeddings.append(batch_embs)
            elif isinstance(batch_embs, list):
                all_embeddings.extend(batch_embs)

        logger.info(f"[GeminiLLMClient] Successfully generated {len(all_embeddings)} embedding vector(s).")
        return all_embeddings
