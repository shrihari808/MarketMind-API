"""
LanceDB Embedded Vector Store Adapter.
Provides zero-cost, memory-efficient vector storage and nearest-neighbor search
using LanceDB (embedded Apache Arrow columnar format).
Supports semantic news caching and historical document filing archives.
"""

import os
import re
import time
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import lancedb
from app.core.config import get_settings
from app.core.logging import logger
from app.domain.interfaces.vector_store import VectorStore
from app.domain.interfaces.llm import LLMClient
from app.domain.schemas.rag import ScrapedDocument, SourceCitation
from app.infrastructure.llm.gemini import GeminiLLMClient


class LanceVectorStore(VectorStore):
    """
    Embedded vector store running in-process with minimal RAM footprint (<30 MB).
    Stores vectors in local memory or persistent directory using Apache Arrow.
    Provides semantic news caching and historical filings vault search.
    """

    NEWS_CACHE_TABLE = "market_news_cache"
    FILINGS_VAULT_TABLE = "filings_vault"
    VAULT_REGISTRY_TABLE = "vault_registry"

    def __init__(self, llm_client: Optional[LLMClient] = None, db_uri: Optional[str] = None):
        settings = get_settings()
        self.db_uri = db_uri or settings.LANCEDB_URI
        os.makedirs(self.db_uri, exist_ok=True)
        self.db = lancedb.connect(self.db_uri)
        self.llm_client = llm_client or GeminiLLMClient()
        logger.info(f"[LanceVectorStore] Initialized at: {self.db_uri}")

    def _get_table_names(self) -> List[str]:
        """Safely retrieves list of table names across LanceDB versions."""
        try:
            res = self.db.list_tables()
            if hasattr(res, "tables"):
                return res.tables
            if isinstance(res, list):
                return res
            return list(res)
        except Exception:
            try:
                return self.db.table_names()
            except Exception:
                return []

    @staticmethod
    def _sanitize(value: str) -> str:
        """Sanitizes user input to prevent SQL injection in LanceDB where clauses."""
        return re.sub(r"['\"\\]", "", value).strip()

    def _chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
        """Simple character text chunker with overlap."""
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

    # --- Standard VectorStore Interface Methods ---

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
                chunk_id = hashlib.md5(f"{doc.url}_{idx}_{chunk[:30]}".encode()).hexdigest()
                raw_chunks.append({
                    "id": chunk_id,
                    "text": chunk,
                    "url": doc.url,
                    "title": doc.title or "Untitled",
                })
                texts_to_embed.append(chunk)

        if not texts_to_embed:
            return 0

        vectors = await self.llm_client.get_embeddings(texts_to_embed)
        if not vectors or len(vectors) != len(texts_to_embed):
            vectors = [[0.0] * 768 for _ in texts_to_embed]

        for item, vec in zip(raw_chunks, vectors):
            item["vector"] = vec

        def _sync_write():
            table_names = self._get_table_names()
            if collection_name in table_names:
                table = self.db.open_table(collection_name)
                table.add(raw_chunks)
            else:
                table = self.db.create_table(collection_name, data=raw_chunks)
            return len(raw_chunks)

        count = await asyncio.to_thread(_sync_write)
        logger.info(f"[LanceVectorStore] Added {count} chunks to collection '{collection_name}'")
        return count

    async def query_similar(
        self,
        query: str,
        collection_name: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Queries nearest neighbors using query embedding vector."""
        def _sync_query(query_vec: List[float]):
            table_names = self._get_table_names()
            if collection_name not in table_names:
                logger.warning(f"[LanceVectorStore] Table '{collection_name}' does not exist.")
                return []

            table = self.db.open_table(collection_name)
            results = table.search(query_vec).metric("cosine").limit(top_k).to_list()
            return results

        query_vectors = await self.llm_client.get_embeddings([query])
        query_vec = query_vectors[0] if query_vectors else [0.0] * 768

        return await asyncio.to_thread(_sync_query, query_vec)

    async def delete_collection(self, collection_name: str) -> bool:
        """Drops a collection table from LanceDB."""
        def _sync_drop():
            table_names = self._get_table_names()
            if collection_name in table_names:
                self.db.drop_table(collection_name)
                return True
            return False

        return await asyncio.to_thread(_sync_drop)

    # --- Feature 1: Semantic News Cache Methods ---

    async def add_news_passages(
        self,
        passages: List[Dict[str, Any]],
        ticker: Optional[str] = None
    ) -> int:
        """
        Embeds and saves verified news passage chunks into the semantic news cache.
        Each passage dict contains: text, url, title, domain, snippet.
        """
        if not passages:
            return 0

        clean_ticker = self._sanitize(ticker).upper() if ticker else ""
        current_time = time.time()
        iso_now = datetime.now(timezone.utc).isoformat()

        texts_to_embed = [p["text"] for p in passages if p.get("text")]
        if not texts_to_embed:
            return 0

        try:
            vectors = await self.llm_client.get_embeddings(texts_to_embed)
        except Exception as e:
            logger.warning(f"[LanceVectorStore] Failed to generate embeddings for news cache: {e}")
            return 0

        if len(vectors) != len(texts_to_embed):
            return 0

        records: List[Dict[str, Any]] = []
        for idx, (p, vec) in enumerate(zip(passages, vectors)):
            text = p.get("text", "")
            url = p.get("url", "")
            chunk_hash = hashlib.sha256(f"{url}_{text[:80]}".encode()).hexdigest()[:16]
            records.append({
                "id": chunk_hash,
                "text": text,
                "url": url,
                "title": p.get("title", "Market News"),
                "domain": p.get("domain", ""),
                "ticker": clean_ticker,
                "timestamp": current_time,
                "created_at": iso_now,
                "vector": vec,
            })

        def _sync_write_cache():
            tables = self._get_table_names()
            if self.NEWS_CACHE_TABLE in tables:
                tbl = self.db.open_table(self.NEWS_CACHE_TABLE)
                tbl.add(records)
            else:
                self.db.create_table(self.NEWS_CACHE_TABLE, data=records)
            return len(records)

        inserted = await asyncio.to_thread(_sync_write_cache)
        logger.info(f"[LanceVectorStore] Cached {inserted} news passage(s) (ticker='{clean_ticker}').")
        return inserted

    async def query_news_cache(
        self,
        query: str,
        min_timestamp: float,
        ticker: Optional[str] = None,
        top_k: int = 5,
        max_distance: float = 0.20
    ) -> List[Dict[str, Any]]:
        """
        Queries semantic news cache for fresh, highly similar passages.
        max_distance = 0.20 corresponds to cosine similarity >= 0.80.
        """
        def _sync_query(query_vec: List[float]):
            tables = self._get_table_names()
            if self.NEWS_CACHE_TABLE not in tables:
                return []

            tbl = self.db.open_table(self.NEWS_CACHE_TABLE)
            clean_t = self._sanitize(ticker).upper() if ticker else ""

            # Filter by freshness
            where_sql = f"timestamp >= {min_timestamp}"
            if clean_t:
                where_sql += f" AND (ticker = '{clean_t}' OR ticker = '')"

            try:
                results = tbl.search(query_vec).metric("cosine").where(where_sql).limit(top_k * 2).to_list()
            except Exception as e:
                logger.warning(f"[LanceVectorStore] Query news cache failed ({e}). Falling back to unconstrained search.")
                results = tbl.search(query_vec).metric("cosine").limit(top_k).to_list()

            # Filter by similarity threshold
            filtered = []
            seen_texts = set()
            for r in results:
                dist = r.get("_distance", 1.0)
                if dist <= max_distance:
                    snippet_key = r.get("text", "")[:60]
                    if snippet_key not in seen_texts:
                        seen_texts.add(snippet_key)
                        r["score"] = round(max(0.0, 1.0 - dist), 4)
                        filtered.append(r)
                if len(filtered) >= top_k:
                    break
            return filtered

        try:
            vectors = await self.llm_client.get_embeddings([query])
            if not vectors:
                return []
            return await asyncio.to_thread(_sync_query, vectors[0])
        except Exception as e:
            logger.warning(f"[LanceVectorStore] News cache lookup exception: {e}")
            return []

    # --- Feature 2: Historical Document Vault Methods ---

    async def add_filing_chunks(
        self,
        chunks: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> int:
        """
        Embeds and stores multi-page filing/document chunks into the filings vault.
        Also records the document registration in vault_registry.
        """
        if not chunks:
            return 0

        doc_id = metadata["doc_id"]
        ticker = self._sanitize(metadata.get("ticker", "")).upper()
        title = metadata.get("title", "Corporate Filing")
        doc_type = self._sanitize(metadata.get("doc_type", "general"))
        fiscal_year = int(metadata.get("fiscal_year") or 0)
        quarter = self._sanitize(metadata.get("quarter", "")).upper()
        file_name = metadata.get("file_name", "")
        iso_now = datetime.now(timezone.utc).isoformat()

        texts_to_embed = [c["text"] for c in chunks if c.get("text")]
        if not texts_to_embed:
            return 0

        vectors = await self.llm_client.get_embeddings(texts_to_embed)
        if len(vectors) != len(texts_to_embed):
            raise ValueError("Embedding count mismatch while indexing document vault.")

        records: List[Dict[str, Any]] = []
        for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            records.append({
                "id": f"{doc_id}_{idx}",
                "doc_id": doc_id,
                "ticker": ticker,
                "title": title,
                "doc_type": doc_type,
                "fiscal_year": fiscal_year,
                "quarter": quarter,
                "page_number": int(chunk.get("page_number") or 1),
                "file_name": file_name,
                "text": chunk.get("text", ""),
                "vector": vec,
                "created_at": iso_now,
            })

        registry_record = [{
            "doc_id": doc_id,
            "ticker": ticker,
            "title": title,
            "doc_type": doc_type,
            "fiscal_year": fiscal_year,
            "quarter": quarter,
            "file_name": file_name,
            "total_chunks": len(records),
            "created_at": iso_now,
        }]

        def _sync_write_vault():
            tables = self._get_table_names()
            # 1. Write chunk vectors
            if self.FILINGS_VAULT_TABLE in tables:
                vault_tbl = self.db.open_table(self.FILINGS_VAULT_TABLE)
                vault_tbl.add(records)
            else:
                self.db.create_table(self.FILINGS_VAULT_TABLE, data=records)

            # 2. Write document registry metadata
            if self.VAULT_REGISTRY_TABLE in tables:
                reg_tbl = self.db.open_table(self.VAULT_REGISTRY_TABLE)
                try:
                    reg_tbl.delete(f"doc_id = '{doc_id}'")
                except Exception:
                    pass
                reg_tbl.add(registry_record)
            else:
                self.db.create_table(self.VAULT_REGISTRY_TABLE, data=registry_record)

            return len(records)

        inserted = await asyncio.to_thread(_sync_write_vault)
        logger.info(f"[LanceVectorStore] Indexed {inserted} chunks for document '{title}' (doc_id={doc_id}).")
        return inserted

    async def query_filings(
        self,
        query: str,
        ticker: Optional[str] = None,
        doc_type: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        top_k: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Executes semantic vector search over the historical filings vault with
        optional Apache Arrow metadata filters (ticker, doc_type, fiscal_year).
        """
        def _sync_query_vault(query_vec: List[float]):
            tables = self._get_table_names()
            if self.FILINGS_VAULT_TABLE not in tables:
                logger.info("[LanceVectorStore] Filings vault table is empty.")
                return []

            tbl = self.db.open_table(self.FILINGS_VAULT_TABLE)
            conds = []
            if ticker and ticker.strip():
                clean_t = self._sanitize(ticker).upper()
                conds.append(f"ticker = '{clean_t}'")
            if doc_type and doc_type.strip():
                clean_dt = self._sanitize(doc_type)
                conds.append(f"doc_type = '{clean_dt}'")
            if fiscal_year and fiscal_year > 0:
                conds.append(f"fiscal_year = {fiscal_year}")

            where_sql = " AND ".join(conds) if conds else None
            logger.debug(f"[LanceVectorStore] Vault query where clause: {where_sql}")

            try:
                search_builder = tbl.search(query_vec).metric("cosine")
                if where_sql:
                    search_builder = search_builder.where(where_sql)
                results = search_builder.limit(top_k).to_list()
            except Exception as e:
                logger.warning(f"[LanceVectorStore] Filtered vault search failed ({e}). Falling back to unfiltered search.")
                results = tbl.search(query_vec).metric("cosine").limit(top_k).to_list()

            for r in results:
                dist = r.get("_distance", 1.0)
                r["score"] = round(max(0.0, 1.0 - dist), 4)

            return results

        vectors = await self.llm_client.get_embeddings([query])
        if not vectors:
            return []

        return await asyncio.to_thread(_sync_query_vault, vectors[0])

    async def list_vault_documents(self, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all registered filings/documents in the vault."""
        def _sync_list():
            tables = self._get_table_names()
            if self.VAULT_REGISTRY_TABLE not in tables:
                return []

            reg_tbl = self.db.open_table(self.VAULT_REGISTRY_TABLE)
            clean_t = self._sanitize(ticker).upper() if ticker else None

            docs = reg_tbl.to_arrow().to_pylist()
            if clean_t:
                return [d for d in docs if (d.get("ticker") or "").upper() == clean_t]
            return docs

        return await asyncio.to_thread(_sync_list)

    async def delete_vault_document(self, doc_id: str) -> bool:
        """Deletes a document and all its indexed vector chunks from the vault."""
        clean_id = self._sanitize(doc_id)

        def _sync_delete():
            tables = self._get_table_names()
            if self.FILINGS_VAULT_TABLE in tables:
                vault_tbl = self.db.open_table(self.FILINGS_VAULT_TABLE)
                vault_tbl.delete(f"doc_id = '{clean_id}'")

            if self.VAULT_REGISTRY_TABLE in tables:
                reg_tbl = self.db.open_table(self.VAULT_REGISTRY_TABLE)
                reg_tbl.delete(f"doc_id = '{clean_id}'")
            return True

        return await asyncio.to_thread(_sync_delete)

    async def delete_vault_ticker(self, ticker: str) -> bool:
        """Deletes all filings and vector chunks for a specific company ticker."""
        clean_t = self._sanitize(ticker).upper()

        def _sync_delete_ticker():
            tables = self._get_table_names()
            if self.FILINGS_VAULT_TABLE in tables:
                vault_tbl = self.db.open_table(self.FILINGS_VAULT_TABLE)
                vault_tbl.delete(f"ticker = '{clean_t}'")

            if self.VAULT_REGISTRY_TABLE in tables:
                reg_tbl = self.db.open_table(self.VAULT_REGISTRY_TABLE)
                reg_tbl.delete(f"ticker = '{clean_t}'")
            return True

        return await asyncio.to_thread(_sync_delete_ticker)
