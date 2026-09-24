"""
Google Gemini AI Engine Adapter.
Implements the LLMClient protocol using the official modern Google GenAI SDK (google-genai)
with native async streaming, Pydantic structured output, multimodal document analysis,
and batched text embeddings.
"""

import asyncio
from typing import AsyncIterator, Optional, Type, TypeVar, List
from pydantic import BaseModel
from google import genai
from google.genai import types

from app.core.config import get_settings
from app.core.logging import logger
from app.domain.interfaces.llm import LLMClient

T = TypeVar("T", bound=BaseModel)


class GeminiLLMClient(LLMClient):
    """Concrete Google Gemini AI adapter using official modern google-genai SDK."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self.embedding_model_name = settings.GEMINI_EMBEDDING_MODEL
        self._client: Optional[genai.Client] = None

        if self.api_key:
            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"Gemini client initialized with model: {self.model_name}")
        else:
            logger.warning("GEMINI_API_KEY not configured. Set it in .env to enable Gemini features.")

    def _get_client(self) -> genai.Client:
        if self._client:
            return self._client
        settings = get_settings()
        if settings.GEMINI_API_KEY:
            self.api_key = settings.GEMINI_API_KEY
            self._client = genai.Client(api_key=self.api_key)
            return self._client
        raise ValueError("GEMINI_API_KEY is required but not configured.")

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> AsyncIterator[str]:
        """Streams generated tokens asynchronously using client.aio."""
        client = self._get_client()
        settings = get_settings()
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        logger.debug(f"[GeminiLLMClient] Initiating stream with model={self.model_name}, temp={temp}, prompt_len={len(prompt)}")

        config = types.GenerateContentConfig(
            temperature=temp,
            system_instruction=system_prompt if system_prompt else None,
        )

        stream = await client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        token_count = 0
        async for chunk in stream:
            if chunk.text:
                token_count += 1
                yield chunk.text
                await asyncio.sleep(0)

        logger.debug(f"[GeminiLLMClient] Stream completed. Yielded {token_count} chunks.")

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generates a complete textual response."""
        client = self._get_client()
        settings = get_settings()
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        logger.debug(f"[GeminiLLMClient] Generating text with model={self.model_name}, temp={temp}, prompt_len={len(prompt)}")

        config = types.GenerateContentConfig(
            temperature=temp,
            system_instruction=system_prompt if system_prompt else None,
        )

        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        text_out = response.text or ""
        logger.debug(f"[GeminiLLMClient] Generated {len(text_out)} chars of text response.")
        return text_out

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_prompt: Optional[str] = None
    ) -> T:
        """Generates a structured output adhering strictly to the provided Pydantic model."""
        client = self._get_client()
        logger.debug(f"[GeminiLLMClient] Generating structured output for schema: {response_schema.__name__}")

        config = types.GenerateContentConfig(
            temperature=0.0,
            system_instruction=system_prompt if system_prompt else None,
            response_mime_type="application/json",
            response_schema=response_schema,
        )

        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        # Use native parsed model if available, otherwise validate json string
        if response.parsed and isinstance(response.parsed, response_schema):
            return response.parsed
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
        client = self._get_client()
        logger.info(f"[GeminiLLMClient] Starting multimodal stream for {len(file_bytes):,} bytes ({mime_type})")

        part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)

        config = types.GenerateContentConfig(
            system_instruction=system_prompt if system_prompt else None,
        )

        stream = await client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=[part, prompt],
            config=config,
        )

        chunk_count = 0
        async for chunk in stream:
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
        client = self._get_client()
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

            model_to_use = self.embedding_model_name
            if "text-embedding-004" in model_to_use:
                model_to_use = "gemini-embedding-001"

            try:
                response = await client.aio.models.embed_content(
                    model=model_to_use,
                    contents=batch,
                    config=types.EmbedContentConfig(output_dimensionality=768)
                )
            except Exception as e:
                if model_to_use != "gemini-embedding-001":
                    logger.warning(f"[GeminiLLMClient] Model '{model_to_use}' failed ({e}). Falling back to 'gemini-embedding-001'.")
                    response = await client.aio.models.embed_content(
                        model="gemini-embedding-001",
                        contents=batch,
                        config=types.EmbedContentConfig(output_dimensionality=768)
                    )
                else:
                    raise e

            if response and response.embeddings:
                for emb in response.embeddings:
                    if emb.values:
                        all_embeddings.append(list(emb.values))

        logger.info(f"[GeminiLLMClient] Successfully generated {len(all_embeddings)} embedding vector(s).")
        return all_embeddings
