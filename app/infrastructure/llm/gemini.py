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
        temperature: float = 0.2
    ) -> AsyncIterator[str]:
        """Streams generated tokens asynchronously."""
        self._ensure_configured()
        
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(temperature=temperature)
        )

        # Run synchronous generate_content in thread with stream=True
        def _sync_stream():
            return model.generate_content(prompt, stream=True)

        response = await asyncio.to_thread(_sync_stream)
        
        for chunk in response:
            if chunk.text:
                yield chunk.text
                await asyncio.sleep(0)  # Yield control to event loop

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2
    ) -> str:
        """Generates a complete textual response."""
        self._ensure_configured()

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(temperature=temperature)
        )

        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text if response and response.text else ""

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_prompt: Optional[str] = None
    ) -> T:
        """Generates a structured output adhering strictly to the provided Pydantic model."""
        self._ensure_configured()

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
        for chunk in response:
            if chunk.text:
                yield chunk.text
                await asyncio.sleep(0)

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings using Gemini text-embedding-004."""
        self._ensure_configured()

        def _embed():
            result = genai.embed_content(
                model=self.embedding_model_name,
                content=texts,
                task_type="retrieval_document"
            )
            return result.get("embedding", [])

        embeddings = await asyncio.to_thread(_embed)
        # Handle single vs batch output from SDK
        if texts and isinstance(embeddings, list) and len(embeddings) > 0 and isinstance(embeddings[0], float):
            return [embeddings]
        return embeddings
