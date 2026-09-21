"""
Vector Store Interface.
Defines contracts for semantic indexing, storage, and retrieval of passage embeddings.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from app.domain.schemas.rag import ScrapedDocument


class VectorStore(ABC):
    """Abstract Base Class for semantic vector storage."""

    @abstractmethod
    async def add_documents(
        self,
        documents: List[ScrapedDocument],
        collection_name: str
    ) -> int:
        """Chunks, embeds, and indexes documents into the vector store."""
        pass

    @abstractmethod
    async def query_similar(
        self,
        query: str,
        collection_name: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieves the top-k most semantically relevant document chunks."""
        pass

    @abstractmethod
    async def delete_collection(self, collection_name: str) -> bool:
        """Deletes an entire collection or namespace."""
        pass
