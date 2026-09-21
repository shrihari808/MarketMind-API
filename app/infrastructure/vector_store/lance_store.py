"""
LanceDB Embedded Vector Store Adapter.
Provides zero-cost, memory-efficient vector storage and nearest-neighbor search
using LanceDB (embedded Apache Arrow columnar format).
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
import pyarrow as pa
import lancedb
from app.core.config import get_settings
from app.core.logging import logger
from app.domain.interfaces.vector_store import VectorStore
from app.domain.interfaces.llm import LLMClient
from app.domain.schemas.rag import ScrapedDocument


class LanceVectorStore(VectorStore):
    """
    Embedded vector store running in-process with minimal RAM footprint (<30 MB).
    Stores vectors in local memory or persistent directory using Apache Arrow.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, db_uri: Optional[str] = None):
        settings = get_settings()
        self.db_uri = db_uri or os.path.join("./data", "lancedb")
        os.makedirs(self.db_uri, exist_ok=True)
        self.db = lancedb.connect(self.db_uri)
        self.llm_client = llm_client
        logger.info(f"LanceDB vector store initialized at: {self.db_uri}")

    def _chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
        """Simple, fast character text chunker with overlap."""
        chunks = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunks.append(text[start:end])
            if end >= text_len:
                break
            start += chunk_size - overlap
        return chunks

    async def add_documents(
        self,
        documents: List[ScrapedDocument],
        collection_name: str
    ) -> int:
        """Chunks, embeds, and stores documents in LanceDB table."""
        if not documents:
            return 0

        raw_chunks: List[Dict[str, Any]] = []
        texts_to_embed: List[str] = []

        for doc in documents:
            if not doc.content:
                continue
            chunks = self._chunk_text(doc.content)
            for idx, chunk in enumerate(chunks):
                raw_chunks.append({
                    "id": f"{doc.url}_{idx}",
                    "text": chunk,
                    "url": doc.url,
                    "title": doc.title,
                })
                texts_to_embed.append(chunk)

        if not texts_to_embed:
            return 0

        # Generate embeddings if LLMClient available, else mock vector for test
        if self.llm_client:
            vectors = await self.llm_client.get_embeddings(texts_to_embed)
        else:
            # Fallback zero-vector placeholder if embeddings client not passed
            vectors = [[0.0] * 768 for _ in texts_to_embed]

        for item, vec in zip(raw_chunks, vectors):
            item["vector"] = vec

        def _sync_write():
            table_names = self.db.list_tables()
            if collection_name in table_names:
                table = self.db.open_table(collection_name)
                table.add(raw_chunks)
            else:
                table = self.db.create_table(collection_name, data=raw_chunks)
            return len(raw_chunks)

        count = await asyncio.to_thread(_sync_write)
        logger.info(f"Added {count} chunks to LanceDB collection '{collection_name}'")
        return count

    async def query_similar(
        self,
        query: str,
        collection_name: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Queries nearest neighbors using query embedding vector."""
        def _sync_query(query_vec: List[float]):
            if collection_name not in self.db.list_tables():
                logger.warning(f"LanceDB table '{collection_name}' does not exist.")
                return []

            table = self.db.open_table(collection_name)
            results = table.search(query_vec).limit(top_k).to_list()
            return results

        if self.llm_client:
            query_vectors = await self.llm_client.get_embeddings([query])
            query_vec = query_vectors[0] if query_vectors else [0.0] * 768
        else:
            query_vec = [0.0] * 768

        return await asyncio.to_thread(_sync_query, query_vec)

    async def delete_collection(self, collection_name: str) -> bool:
        """Drops a collection table from LanceDB."""
        def _sync_drop():
            if collection_name in self.db.list_tables():
                self.db.drop_table(collection_name)
                return True
            return False

        return await asyncio.to_thread(_sync_drop)
