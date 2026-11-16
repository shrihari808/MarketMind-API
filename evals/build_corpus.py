"""
Builds a frozen, reproducible corpus of real scraped financial web documents
for Recall@k evaluation across N documents.
"""

import asyncio
import json
import os
import re
from typing import Any, Dict, List

from app.infrastructure.scrapers.web_scraper import TrafilaturaWebScraper
from app.infrastructure.search.duckduckgo import DuckDuckGoSearcher


TOPIC_QUERIES: List[Dict[str, Any]] = [
    {
        "id": "q_nvda",
        "query": "Nvidia data center revenue earnings outlook",
        "country": "US",
        "must_any": ["nvidia", "nvda"],
        "topic_any": ["data center", "revenue", "earnings", "gpu", "ai", "blackwell", "chip"],
    },
    {
        "id": "q_reliance",
        "query": "Reliance Industries quarterly results retail telecom",
        "country": "IN",
        "must_any": ["reliance", "jio"],
        "topic_any": ["quarter", "results", "profit", "revenue", "retail", "telecom", "ebitda"],
    },
    {
        "id": "q_fed",
        "query": "Federal Reserve interest rate decision inflation",
        "country": "US",
        "must_any": ["federal reserve", "fed", "fomc", "powell"],
        "topic_any": ["interest rate", "rate cut", "rate hike", "inflation", "rates", "policy"],
    },
    {
        "id": "q_tcs",
        "query": "TCS Q2 earnings operating margin deal pipeline",
        "country": "IN",
        "must_any": ["tcs", "tata consultancy"],
        "topic_any": ["earnings", "profit", "revenue", "margin", "deal", "quarter", "results"],
    },
    {
        "id": "q_aapl",
        "query": "Apple iPhone sales growth services revenue",
        "country": "US",
        "must_any": ["apple", "aapl"],
        "topic_any": ["iphone", "services", "revenue", "sales", "earnings", "quarter"],
    },
    {
        "id": "q_hdfc",
        "query": "HDFC Bank net profit NIM asset quality",
        "country": "IN",
        "must_any": ["hdfc bank", "hdfc"],
        "topic_any": ["profit", "nim", "net interest", "deposit", "loan", "npa", "quarter"],
    },
    {
        "id": "q_tsla",
        "query": "Tesla vehicle deliveries automotive gross margin",
        "country": "US",
        "must_any": ["tesla", "tsla"],
        "topic_any": ["deliveries", "margin", "ev", "vehicle", "earnings", "revenue"],
    },
    {
        "id": "q_rbi",
        "query": "RBI monetary policy repo rate inflation forecast",
        "country": "IN",
        "must_any": ["rbi", "reserve bank of india"],
        "topic_any": ["repo rate", "monetary policy", "inflation", "mpc", "rate"],
    },
    {
        "id": "q_msft",
        "query": "Microsoft Azure AI cloud growth capex",
        "country": "US",
        "must_any": ["microsoft", "msft"],
        "topic_any": ["azure", "cloud", "ai", "capex", "revenue", "earnings"],
    },
    {
        "id": "q_infy",
        "query": "Infosys revenue guidance AI transformation deals",
        "country": "IN",
        "must_any": ["infosys", "infy"],
        "topic_any": ["guidance", "revenue", "profit", "deal", "ai", "margin", "quarter"],
    },
    {
        "id": "q_amzn",
        "query": "Amazon AWS cloud operating income retail margin",
        "country": "US",
        "must_any": ["amazon", "amzn"],
        "topic_any": ["aws", "cloud", "operating income", "retail", "earnings", "revenue"],
    },
    {
        "id": "q_icici",
        "query": "ICICI Bank net interest income deposit growth",
        "country": "IN",
        "must_any": ["icici bank", "icici"],
        "topic_any": ["net interest", "profit", "deposit", "loan", "npa", "quarter"],
    },
    {
        "id": "q_oil",
        "query": "Crude oil Brent prices OPEC supply outlook",
        "country": "US",
        "must_any": ["brent", "crude oil", "opec"],
        "topic_any": ["oil", "barrel", "supply", "demand", "price", "prices"],
    },
    {
        "id": "q_gold",
        "query": "Gold price rally central bank demand outlook",
        "country": "IN",
        "must_any": ["gold"],
        "topic_any": ["price", "prices", "rally", "ounce", "central bank", "bullion", "demand"],
    },
    {
        "id": "q_amd",
        "query": "AMD AI GPU MI300 data center competition",
        "country": "US",
        "must_any": ["amd", "advanced micro devices"],
        "topic_any": ["data center", "gpu", "ai", "mi300", "mi350", "chip", "revenue"],
    },
    {
        "id": "q_tatamotors",
        "query": "Tata Motors JLR EV sales margin outlook",
        "country": "IN",
        "must_any": ["tata motors", "jlr", "jaguar land rover"],
        "topic_any": ["sales", "ev", "margin", "profit", "revenue", "quarter", "vehicle"],
    },
]


def is_topically_relevant(doc: Dict[str, Any], qspec: Dict[str, Any]) -> bool:
    """Checks explicit entity + topic relevance across title, snippet, and body."""
    haystack = f"{doc.get('title', '')}\n{doc.get('snippet', '')}\n{doc.get('content', '')}".lower()
    must_ok = any(re.search(rf"\b{re.escape(term)}\b", haystack) for term in qspec["must_any"])
    if not must_ok:
        return False
    topic_hits = sum(1 for term in qspec["topic_any"] if term in haystack)
    return topic_hits >= 2


async def build_corpus(
    corpus_path: str = "evals/corpus.jsonl",
    qrels_path: str = "evals/queries_with_qrels.json",
    per_query_results: int = 6,
) -> None:
    searcher = DuckDuckGoSearcher()
    scraper = TrafilaturaWebScraper(timeout_seconds=8)

    url_to_candidate: Dict[str, Dict[str, Any]] = {}

    for qspec in TOPIC_QUERIES:
        query = qspec["query"]
        country = qspec["country"]
        # Use general web search + past-month news so queries match real entity articles cleanly
        news_res, web_res = await asyncio.gather(
            searcher.search_news(query, max_results=per_query_results, country=country, timelimit="m"),
            searcher.search(query, max_results=per_query_results, country=country, timelimit="y"),
        )
        for item in news_res + web_res:
            if item.url and item.url not in url_to_candidate:
                url_to_candidate[item.url] = {
                    "url": item.url,
                    "title": item.title,
                    "snippet": item.snippet or "",
                    "publication_date": item.publication_date,
                    "domain": item.domain or "",
                    "origin_query_id": qspec["id"],
                }

    urls = list(url_to_candidate.keys())
    print(f"Collected {len(urls)} unique candidate URLs. Scraping in batches of 15...")

    scraped_docs: List[Any] = []
    for i in range(0, len(urls), 15):
        batch = urls[i:i + 15]
        batch_res = await scraper.scrape_many(batch)
        scraped_docs.extend(batch_res)

    corpus: List[Dict[str, Any]] = []
    for doc in scraped_docs:
        if not doc.success or not doc.content or len(doc.content.split()) < 80:
            continue
        meta = url_to_candidate.get(doc.url) or next(
            (v for k, v in url_to_candidate.items() if k in doc.url or doc.url in k),
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

    os.makedirs(os.path.dirname(corpus_path), exist_ok=True)
    with open(corpus_path, "w", encoding="utf-8") as f:
        for row in corpus:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    qrels_output: List[Dict[str, Any]] = []
    for qspec in TOPIC_QUERIES:
        relevant_ids = [doc["doc_id"] for doc in corpus if is_topically_relevant(doc, qspec)]
        qrels_output.append({
            "id": qspec["id"],
            "query": qspec["query"],
            "country": qspec["country"],
            "relevant_doc_ids": relevant_ids,
            "relevant_count": len(relevant_ids),
        })

    with open(qrels_path, "w", encoding="utf-8") as f:
        json.dump(qrels_output, f, indent=2)

    print(f"Saved {len(corpus)} scraped documents to {corpus_path}")
    for q in qrels_output:
        print(f"  {q['id']:14s} | rel={q['relevant_count']:2d} | {q['query']}")


if __name__ == "__main__":
    asyncio.run(build_corpus())
