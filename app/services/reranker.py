"""
Lightweight Passage Reranker Module.
Provides pure-Python BM25Okapi scoring with domain diversification, plus an optional
hybrid semantic booster using Gemini embeddings without loading local neural models.
"""

import math
import re
from typing import List, Optional, Dict
from urllib.parse import urlparse
from app.core.logging import logger
from app.domain.interfaces.llm import LLMClient
from app.domain.schemas.rag import PassageChunk


class BM25Reranker:
    """
    Zero-dependency, pure-Python BM25Okapi passage reranker.
    Operates in <100 KB RAM and sub-millisecond execution time.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Simple whitespace and alphanumeric tokenizer."""
        cleaned = re.sub(r"[^\w\s\.\-%]", " ", text.lower())
        tokens = [t.strip() for t in cleaned.split() if len(t.strip()) > 1]
        return tokens

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extracts clean base domain from URL."""
        if not url:
            return "unknown"
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain or "unknown"
        except Exception:
            return "unknown"

    def rerank(
        self,
        query: str,
        passages: List[PassageChunk],
        top_k: int = 5,
        max_per_domain: int = 2
    ) -> List[PassageChunk]:
        """
        Scores passages using BM25Okapi and applies domain diversification.

        Args:
            query: The search or question query string.
            passages: Candidate passage chunks to rank.
            top_k: Maximum number of passages to return.
            max_per_domain: Maximum number of passages allowed from the same source domain.

        Returns:
            List[PassageChunk]: Top reranked and diversified passages sorted by score.
        """
        if not passages:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return passages[:top_k]

        num_docs = len(passages)
        doc_tokens_list = [self.tokenize(p.text) for p in passages]
        doc_lengths = [len(tokens) for tokens in doc_tokens_list]
        avg_doc_len = sum(doc_lengths) / num_docs if num_docs > 0 else 1.0

        # Calculate document frequency for each query term
        doc_freqs: Dict[str, int] = {}
        for q in set(query_tokens):
            df = sum(1 for tokens in doc_tokens_list if q in tokens)
            doc_freqs[q] = df

        # Compute BM25 scores
        scored_passages: List[PassageChunk] = []
        for i, (passage, doc_tokens, doc_len) in enumerate(zip(passages, doc_tokens_list, doc_lengths)):
            score = 0.0
            term_counts: Dict[str, int] = {}
            for token in doc_tokens:
                term_counts[token] = term_counts.get(token, 0) + 1

            for q in query_tokens:
                if q not in term_counts:
                    continue
                tf = term_counts[q]
                df = doc_freqs.get(q, 0)

                # Standard Okapi IDF with smoothing
                idf = math.log((num_docs - df + 0.5) / (df + 0.5) + 1.0)
                if idf < 0:
                    idf = 0.01

                # Term saturation & length normalization
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / avg_doc_len))
                score += idf * (numerator / denominator)

            # Assign score to cloned or updated passage
            scored = passage.model_copy(update={"score": round(score, 4)})
            scored_passages.append(scored)

        # Sort descending by BM25 score
        scored_passages.sort(key=lambda x: x.score, reverse=True)

        # Apply domain diversification filter
        diversified: List[PassageChunk] = []
        domain_counts: Dict[str, int] = {}

        for p in scored_passages:
            domain = self.extract_domain(p.source.url if p.source else "")
            count = domain_counts.get(domain, 0)
            if count < max_per_domain:
                diversified.append(p)
                domain_counts[domain] = count + 1
            if len(diversified) >= top_k:
                break

        logger.debug(
            f"BM25 Reranker: Scored {len(passages)} passages. Selected top {len(diversified)} "
            f"across {len(domain_counts)} domains."
        )
        return diversified


class HybridReranker:
    """
    Hybrid reranker combining lexical BM25 with dense Gemini API embeddings.
    Zero local neural model weights or PyTorch memory allocated on server.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, alpha: float = 0.4):
        """
        Args:
            llm_client: LLMClient instance supporting get_embeddings.
            alpha: Weight for BM25 lexical score (1 - alpha is semantic weight).
        """
        self.bm25 = BM25Reranker()
        self.llm_client = llm_client
        self.alpha = alpha

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 <= 0 or norm2 <= 0:
            return 0.0
        return dot / (norm1 * norm2)

    async def rerank(
        self,
        query: str,
        passages: List[PassageChunk],
        top_k: int = 5,
        max_per_domain: int = 2
    ) -> List[PassageChunk]:
        """
        Performs hybrid reranking using BM25 and Gemini text-embedding-004 over the API.
        Falls back seamlessly to BM25 if embedding API is unavailable.
        """
        if not passages:
            return []

        # Step 1: Pre-filter candidate pool with BM25 if pool is large
        candidate_pool = self.bm25.rerank(
            query=query,
            passages=passages,
            top_k=min(len(passages), top_k * 3),
            max_per_domain=max_per_domain * 2
        )

        # If no LLMClient configured, return pure BM25 results
        if not self.llm_client:
            return candidate_pool[:top_k]

        try:
            # Step 2: Fetch embeddings via API
            texts_to_embed = [query] + [p.text[:500] for p in candidate_pool]
            embeddings = await self.llm_client.get_embeddings(texts_to_embed)

            if not embeddings or len(embeddings) < len(texts_to_embed):
                logger.warning("Embeddings incomplete. Falling back to BM25 ranking.")
                return candidate_pool[:top_k]

            query_emb = embeddings[0]
            passage_embs = embeddings[1:]

            # Normalize BM25 scores between 0 and 1
            max_bm25 = max([p.score for p in candidate_pool] or [1.0])
            if max_bm25 <= 0:
                max_bm25 = 1.0

            hybrid_scored: List[PassageChunk] = []
            for passage, p_emb in zip(candidate_pool, passage_embs):
                sim = self._cosine_similarity(query_emb, p_emb)
                norm_bm25 = passage.score / max_bm25
                hybrid_score = (self.alpha * norm_bm25) + ((1.0 - self.alpha) * sim)
                scored = passage.model_copy(update={"score": round(hybrid_score, 4)})
                hybrid_scored.append(scored)

            hybrid_scored.sort(key=lambda x: x.score, reverse=True)

            # Apply domain diversification
            diversified: List[PassageChunk] = []
            domain_counts: Dict[str, int] = {}
            for p in hybrid_scored:
                domain = self.bm25.extract_domain(p.source.url if p.source else "")
                count = domain_counts.get(domain, 0)
                if count < max_per_domain:
                    diversified.append(p)
                    domain_counts[domain] = count + 1
                if len(diversified) >= top_k:
                    break

            return diversified

        except Exception as e:
            logger.warning(f"Hybrid reranking encountered error ({e}). Using BM25 fallback.")
            return candidate_pool[:top_k]
