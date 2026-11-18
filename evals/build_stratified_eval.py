"""
Expands the real scraped financial web corpus and builds tight 1-3 gold-document
relevance labels across the 45 in-domain stratified queries.
"""

import asyncio
import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.scrapers.web_scraper import TrafilaturaWebScraper
from app.infrastructure.search.duckduckgo import DuckDuckGoSearcher


def load_existing_corpus(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    docs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                docs.append(json.loads(line))
    return docs


def score_gold_fit(doc: Dict[str, Any], concepts: List[List[str]]) -> Tuple[bool, float]:
    """
    Checks strict multi-concept match across all concept groups.
    Returns (is_qualified, specificity_score) independent of BM25/freshness.
    """
    title = (doc.get("title") or "").lower()
    body = f"{doc.get('snippet', '')}\n{doc.get('content', '')}".lower()
    full = f"{title}\n{body}"

    group_scores: List[float] = []
    for group in concepts:
        title_hits = sum(1 for term in group if re.search(rf"\b{re.escape(term)}\b", title))
        full_hits = sum(1 for term in group if re.search(rf"\b{re.escape(term)}\b", full))
        if full_hits == 0:
            return False, 0.0
        # Reward title alignment and distinct concept coverage
        group_scores.append(2.0 * title_hits + min(full_hits, 3))

    return True, sum(group_scores)


async def build_stratified_corpus(
    queries_path: str = "evals/stratified_queries.json",
    base_corpus_path: str = "evals/corpus.jsonl",
    out_corpus_path: str = "evals/corpus_v2.jsonl",
    out_qrels_path: str = "evals/stratified_qrels.json",
) -> None:
    with open(queries_path, "r", encoding="utf-8") as f:
        queries = json.load(f)

    existing_docs = load_existing_corpus(base_corpus_path)
    existing_urls = {d["url"] for d in existing_docs}
    print(f"Loaded {len(existing_docs)} existing docs from {base_corpus_path}")

    searcher = DuckDuckGoSearcher()
    scraper = TrafilaturaWebScraper(timeout_seconds=4.0, max_concurrency=12, cache_ttl_seconds=0)

    # Fetch extra candidate URLs for all 45 in-domain queries (focusing on new/comparative topics)
    in_domain = [q for q in queries if q["expected_is_financial"]]
    url_meta: Dict[str, Dict[str, Any]] = {}

    for idx, q in enumerate(in_domain):
        # Fetch for all comparative + breaking + missing tickers
        if q["category"] == "multi_hop_comparative" or idx % 2 == 0 or any(
            k in q["id"] for k in ("fund_12", "fund_15", "news_07", "news_08", "comp_12")
        ):
            news_res, web_res = await asyncio.gather(
                searcher.search_news(q["query"], max_results=4, country=q["country"], timelimit="m"),
                searcher.search(q["query"], max_results=4, country=q["country"], timelimit="y"),
            )
            for item in news_res + web_res:
                if item.url and item.url not in existing_urls and item.url not in url_meta:
                    url_meta[item.url] = {
                        "url": item.url,
                        "title": item.title,
                        "snippet": item.snippet or "",
                        "publication_date": item.publication_date,
                        "domain": item.domain or "",
                        "origin_query_id": q["id"],
                    }

    new_urls = list(url_meta.keys())
    print(f"Collected {len(new_urls)} new candidate URLs. Scraping...")

    new_scraped = []
    for i in range(0, len(new_urls), 20):
        batch = new_urls[i:i + 20]
        new_scraped.extend(await scraper.scrape_many(batch))

    corpus = list(existing_docs)
    for doc in new_scraped:
        if not doc.success or not doc.content or len(doc.content.split()) < 80:
            continue
        if doc.url in existing_urls:
            continue
        existing_urls.add(doc.url)
        meta = url_meta.get(doc.url) or next(
            (v for k, v in url_meta.items() if k in doc.url or doc.url in k),
            {},
        )
        doc_id = f"doc_{len(corpus) + 1:03d}"
        corpus.append({
            "doc_id": doc_id,
            "url": doc.url,
            "domain": meta.get("domain", ""),
            "title": doc.title or meta.get("title", "Financial News"),
            "snippet": meta.get("snippet", "") or doc.content[:280],
            "publication_date": doc.published_date or meta.get("publication_date"),
            "word_count": len(doc.content.split()),
            "content": doc.content,
            "origin_query_id": meta.get("origin_query_id", ""),
        })

    os.makedirs(os.path.dirname(out_corpus_path), exist_ok=True)
    with open(out_corpus_path, "w", encoding="utf-8") as f:
        for row in corpus:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Assign tight 1-3 gold documents per in-domain query
    qrels_out: List[Dict[str, Any]] = []
    zero_gold = []
    for q in in_domain:
        candidates: List[Tuple[float, str, str]] = []
        for doc in corpus:
            ok, spec = score_gold_fit(doc, q["concepts"])
            if ok:
                candidates.append((spec, doc["doc_id"], doc["title"]))
        # Fallback: if comparative query had 0 docs with all 3 groups, require first 2 entity groups
        if not candidates and len(q["concepts"]) >= 2:
            for doc in corpus:
                ok, spec = score_gold_fit(doc, q["concepts"][:2])
                if ok:
                    candidates.append((spec, doc["doc_id"], doc["title"]))
        # Secondary fallback if still 0 (e.g., comparative article only covers one side + topic)
        if not candidates and len(q["concepts"]) >= 3:
            for doc in corpus:
                ok, spec = score_gold_fit(doc, [q["concepts"][0], q["concepts"][2]])
                if ok:
                    candidates.append((spec * 0.5, doc["doc_id"], doc["title"]))

        candidates.sort(key=lambda x: x[0], reverse=True)
        gold = candidates[:3]
        if not gold:
            zero_gold.append(q["id"])
        qrels_out.append({
            "id": q["id"],
            "category": q["category"],
            "query": q["query"],
            "country": q["country"],
            "relevant_doc_ids": [g[1] for g in gold],
            "gold_titles": [g[2] for g in gold],
            "relevant_count": len(gold),
        })

    with open(out_qrels_path, "w", encoding="utf-8") as f:
        json.dump(qrels_out, f, indent=2)

    avg_rel = sum(q["relevant_count"] for q in qrels_out) / max(len(qrels_out), 1)
    print(f"Saved {len(corpus)} documents to {out_corpus_path}")
    print(f"Labeled {len(qrels_out)} in-domain queries (avg gold docs/query = {avg_rel:.2f}, zero-gold = {zero_gold})")


if __name__ == "__main__":
    asyncio.run(build_stratified_corpus())
