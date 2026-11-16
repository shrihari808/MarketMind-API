"""
Evaluates Web RAG retrieval Recall@k, HitRate@k, and MRR across N documents.
Tests the actual production chunker, BM25Reranker, FreshnessReranker,
Pre-Scrape Citation Filter, and Two-Stage Web RAG Funnel.
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.domain.schemas.rag import PassageChunk, SourceCitation
from app.services.reranker import BM25Reranker, FreshnessReranker, HybridReranker
from app.services.web_rag import WebRAGService


def load_corpus(corpus_path: str) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    return docs


def load_qrels(qrels_path: str) -> List[Dict[str, Any]]:
    with open(qrels_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [q for q in data if q.get("relevant_doc_ids")]


def build_citations_and_passages(
    docs: List[Dict[str, Any]],
    chunk_size: int = 400,
    overlap: int = 50,
    max_chunks_per_doc: int = 8,
) -> Tuple[List[SourceCitation], List[PassageChunk], Dict[str, str]]:
    citations: List[SourceCitation] = []
    passages: List[PassageChunk] = []
    url_to_doc_id: Dict[str, str] = {}

    for idx, doc in enumerate(docs, start=1):
        cit = SourceCitation(
            id=idx,
            title=doc.get("title") or "Untitled",
            url=doc["url"],
            snippet=doc.get("snippet", ""),
            publication_date=doc.get("publication_date"),
            domain=doc.get("domain") or BM25Reranker.extract_domain(doc["url"]),
        )
        citations.append(cit)
        url_to_doc_id[doc["url"]] = doc["doc_id"]

        chunks = WebRAGService._chunk_text(doc["content"], chunk_size=chunk_size, overlap=overlap)
        for c_idx, text_chunk in enumerate(chunks[:max_chunks_per_doc]):
            passages.append(
                PassageChunk(
                    text=text_chunk,
                    source=cit,
                    score=0.0,
                    chunk_index=c_idx,
                )
            )
    return citations, passages, url_to_doc_id


def ordered_unique_doc_ids(ranked_urls: List[str], url_to_doc_id: Dict[str, str]) -> List[str]:
    seen: Set[str] = set()
    ordered: List[str] = []
    for url in ranked_urls:
        doc_id = url_to_doc_id.get(url)
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            ordered.append(doc_id)
    return ordered


def score_ranking(
    retrieved_doc_ids: List[str],
    relevant_doc_ids: Set[str],
    ks: List[int],
) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    if not relevant_doc_ids:
        return metrics

    for k in ks:
        top_docs = set(retrieved_doc_ids[:k])
        hits = len(top_docs & relevant_doc_ids)
        metrics[f"recall@{k}"] = hits / len(relevant_doc_ids)
        metrics[f"hit@{k}"] = 1.0 if hits > 0 else 0.0

    rr = 0.0
    for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
        if doc_id in relevant_doc_ids:
            rr = 1.0 / rank
            break
    metrics["mrr"] = rr
    return metrics


def aggregate_metrics(per_query: List[Dict[str, float]], ks: List[int]) -> Dict[str, float]:
    if not per_query:
        return {}
    agg: Dict[str, float] = {"num_queries": len(per_query)}
    keys = [f"recall@{k}" for k in ks] + [f"hit@{k}" for k in ks] + ["mrr"]
    for key in keys:
        vals = [q[key] for q in per_query if key in q]
        agg[key] = round(sum(vals) / len(vals), 4) if vals else 0.0
    return agg


def subset_for_n(
    full_corpus: List[Dict[str, Any]],
    qrels: List[Dict[str, Any]],
    target_n: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Constructs a deterministic N-document subset preserving relevant docs for queries
    that fit, plus real distractor documents from the rest of the corpus.
    """
    if target_n >= len(full_corpus):
        return full_corpus, qrels

    selected_ids: Set[str] = set()
    included_qrels: List[Dict[str, Any]] = []
    doc_map = {d["doc_id"]: d for d in full_corpus}

    for q in qrels:
        rel_ids = q["relevant_doc_ids"]
        if len(selected_ids | set(rel_ids)) <= target_n:
            selected_ids.update(rel_ids)
            included_qrels.append(q)

    # Fill remaining slots up to target_n with deterministic corpus order
    for doc in full_corpus:
        if len(selected_ids) >= target_n:
            break
        selected_ids.add(doc["doc_id"])

    sub_docs = [doc_map[d["doc_id"]] for d in full_corpus if d["doc_id"] in selected_ids]
    # Re-filter qrels to docs actually in sub_docs
    sub_doc_ids = {d["doc_id"] for d in sub_docs}
    final_qrels = []
    for q in qrels:
        rel = [did for did in q["relevant_doc_ids"] if did in sub_doc_ids]
        if rel:
            final_qrels.append({**q, "relevant_doc_ids": rel, "relevant_count": len(rel)})
    return sub_docs, final_qrels


async def evaluate(
    corpus_path: str,
    qrels_path: str,
    output_path: str,
    ks: List[int],
    n_steps: Optional[List[int]] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    full_corpus = load_corpus(corpus_path)
    full_qrels = load_qrels(qrels_path)
    total_n = len(full_corpus)

    if not n_steps:
        candidates = [25, 50, 75, total_n]
        n_steps = sorted({n for n in candidates if n < total_n} | {total_n})

    bm25 = BM25Reranker()
    freshness = FreshnessReranker()
    hybrid: Optional[HybridReranker] = None
    if settings.GEMINI_API_KEY:
        from app.infrastructure.llm.gemini import GeminiLLMClient
        hybrid = HybridReranker(llm_client=GeminiLLMClient())

    max_k = max(ks)
    results_by_n: List[Dict[str, Any]] = []

    for n in n_steps:
        sub_docs, sub_qrels = subset_for_n(full_corpus, full_qrels, n)
        citations, passages, url_to_doc_id = build_citations_and_passages(
            sub_docs,
            chunk_size=settings.RAG_CHUNK_SIZE,
            overlap=settings.RAG_CHUNK_OVERLAP,
            max_chunks_per_doc=8,
        )

        # Evaluate at each k separately for passage-slot-limited methods (production top_k=k)
        # and also full-ranking metrics
        prefilter_scores: List[Dict[str, float]] = []
        bm25_slot_scores: List[Dict[str, float]] = []
        fresh_slot_scores: List[Dict[str, float]] = []
        funnel_scores: List[Dict[str, float]] = []
        hybrid_slot_scores: List[Dict[str, float]] = []

        for q in sub_qrels:
            query_text = q["query"]
            rel_set = set(q["relevant_doc_ids"])

            # 1. Pre-filter citations (title + snippet -> top_k URLs)
            # Call separately per k because pre_filter_citations short-circuits if len(citations) <= top_k
            pre_q_metrics: Dict[str, float] = {}
            for k in ks:
                pre_k = freshness.pre_filter_citations(query=query_text, citations=citations, top_k=k)
                pre_k_docs = ordered_unique_doc_ids([c.url for c in pre_k], url_to_doc_id)
                pre_q_metrics.update(score_ranking(pre_k_docs, rel_set, [k]))
            pre_full = freshness.pre_filter_citations(
                query=query_text, citations=citations, top_k=max(1, len(citations) - 1)
            )
            pre_q_metrics["mrr"] = score_ranking(
                ordered_unique_doc_ids([c.url for c in pre_full], url_to_doc_id),
                rel_set,
                [],
            )["mrr"]
            prefilter_scores.append(pre_q_metrics)

            # 2. BM25 passage rerank at each k (respecting production passage-slot top_k=k and max_per_domain=2)
            bm25_q_metrics: Dict[str, float] = {}
            fresh_q_metrics: Dict[str, float] = {}
            funnel_q_metrics: Dict[str, float] = {}
            hybrid_q_metrics: Dict[str, float] = {}

            for k in ks:
                bm25_top = bm25.rerank(query=query_text, passages=passages, top_k=k, max_per_domain=2)
                bm25_docs = ordered_unique_doc_ids([p.source.url for p in bm25_top], url_to_doc_id)
                bm25_q_metrics.update(score_ranking(bm25_docs, rel_set, [k]))

                fresh_top = freshness.rerank(query=query_text, passages=passages, top_k=k, max_per_domain=2)
                fresh_docs = ordered_unique_doc_ids([p.source.url for p in fresh_top], url_to_doc_id)
                fresh_q_metrics.update(score_ranking(fresh_docs, rel_set, [k]))

                # Production Two-Stage Funnel: pre-filter to MAX_SCRAPED_SOURCES (5) URLs, then passage rerank top_k
                top5_urls = {
                    c.url
                    for c in freshness.pre_filter_citations(
                        query=query_text,
                        citations=citations,
                        top_k=settings.MAX_SCRAPED_SOURCES,
                    )
                }
                funnel_passages = [p for p in passages if p.source.url in top5_urls]
                funnel_top = freshness.rerank(query=query_text, passages=funnel_passages, top_k=k, max_per_domain=2)
                funnel_docs = ordered_unique_doc_ids([p.source.url for p in funnel_top], url_to_doc_id)
                funnel_q_metrics.update(score_ranking(funnel_docs, rel_set, [k]))

                if hybrid is not None:
                    hyb_top = await hybrid.rerank(query=query_text, passages=passages, top_k=k, max_per_domain=2)
                    hyb_docs = ordered_unique_doc_ids([p.source.url for p in hyb_top], url_to_doc_id)
                    hybrid_q_metrics.update(score_ranking(hyb_docs, rel_set, [k]))

            # MRR over full passage ranking (up to 999)
            bm25_full = bm25.rerank(query=query_text, passages=passages, top_k=len(passages), max_per_domain=2)
            bm25_q_metrics["mrr"] = score_ranking(
                ordered_unique_doc_ids([p.source.url for p in bm25_full], url_to_doc_id),
                rel_set,
                [],
            )["mrr"]
            bm25_slot_scores.append(bm25_q_metrics)

            fresh_full = freshness.rerank(query=query_text, passages=passages, top_k=len(passages), max_per_domain=2)
            fresh_q_metrics["mrr"] = score_ranking(
                ordered_unique_doc_ids([p.source.url for p in fresh_full], url_to_doc_id),
                rel_set,
                [],
            )["mrr"]
            fresh_slot_scores.append(fresh_q_metrics)

            top5_urls_full = {
                c.url
                for c in freshness.pre_filter_citations(
                    query=query_text,
                    citations=citations,
                    top_k=settings.MAX_SCRAPED_SOURCES,
                )
            }
            funnel_passages_full = [p for p in passages if p.source.url in top5_urls_full]
            funnel_full = freshness.rerank(
                query=query_text,
                passages=funnel_passages_full,
                top_k=len(funnel_passages_full),
                max_per_domain=2,
            )
            funnel_q_metrics["mrr"] = score_ranking(
                ordered_unique_doc_ids([p.source.url for p in funnel_full], url_to_doc_id),
                rel_set,
                [],
            )["mrr"]
            funnel_scores.append(funnel_q_metrics)

            if hybrid is not None:
                hybrid_slot_scores.append(hybrid_q_metrics)

        entry: Dict[str, Any] = {
            "N_documents": len(sub_docs),
            "total_passages": len(passages),
            "num_queries": len(sub_qrels),
            "methods": {
                "pre_filter_citations": aggregate_metrics(prefilter_scores, ks),
                "bm25_reranker": aggregate_metrics(bm25_slot_scores, ks),
                "freshness_reranker": aggregate_metrics(fresh_slot_scores, ks),
                "production_two_stage_funnel": aggregate_metrics(funnel_scores, ks),
            },
        }
        if hybrid is not None:
            entry["methods"]["hybrid_reranker"] = aggregate_metrics(hybrid_slot_scores, ks)

        results_by_n.append(entry)

    report = {
        "corpus_path": corpus_path,
        "qrels_path": qrels_path,
        "full_corpus_size": total_n,
        "ks": ks,
        "config": {
            "chunk_size_words": settings.RAG_CHUNK_SIZE,
            "chunk_overlap_words": settings.RAG_CHUNK_OVERLAP,
            "max_chunks_per_doc": 8,
            "max_scraped_sources": settings.MAX_SCRAPED_SOURCES,
            "max_per_domain": 2,
            "half_life_days": settings.RAG_HALF_LIFE_DAYS,
            "relevance_floor": settings.RAG_RELEVANCE_FLOOR,
            "hybrid_reranker_evaluated": hybrid is not None,
        },
        "results_by_N": results_by_n,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Web RAG Recall@k across N documents.")
    parser.add_argument("--corpus", default="evals/corpus.jsonl")
    parser.add_argument("--qrels", default="evals/queries_with_qrels.json")
    parser.add_argument("--output", default="evals/results/recall_results.json")
    parser.add_argument("--ks", nargs="+", type=int, default=[1, 3, 5, 10])
    parser.add_argument("--n-steps", nargs="*", type=int, default=None)
    args = parser.parse_args()

    report = asyncio.run(
        evaluate(
            corpus_path=args.corpus,
            qrels_path=args.qrels,
            output_path=args.output,
            ks=args.ks,
            n_steps=args.n_steps,
        )
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
