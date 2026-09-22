"""
LLM Client Interface.
Defines contracts for streaming, structured output generation, and multimodal analysis.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Type, TypeVar, List
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(ABC):
    """Abstract Base Class for Large Language Model operations."""

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> AsyncIterator[str]:
        """Streams generated tokens asynchronously."""
        pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generates a complete textual response."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_prompt: Optional[str] = None
    ) -> T:
        """Generates a strictly validated response adhering to a Pydantic schema."""
        pass

    @abstractmethod
    async def generate_multimodal_stream(
        self,
        prompt: str,
        file_bytes: bytes,
        mime_type: str = "application/pdf",
        system_prompt: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Streams analysis directly from a multimodal file (e.g., PDF or image)."""
        pass

    @abstractmethod
    async def get_embeddings(
        self,
        texts: List[str],
        batch_size: Optional[int] = None
    ) -> List[List[float]]:
        """Generates semantic embedding vectors for a list of texts with optional batching."""
        pass
