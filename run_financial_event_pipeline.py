# aigptssh/run_financial_event_pipeline.py
import asyncio
from api.graph.zerodha_scraper import scrape_zerodha_pulse
from api.graph.event_extractor import extract_events, generate_brave_query
from api.brave_searcher import BraveNews
from api.dashboard.web_scraper import scrape_urls
from api.graph.neo4j_importer import KnowledgeGraphImporter, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
import os

async def run_financial_event_pipeline():
    """
    Orchestrates the entire financial event knowledge graph pipeline.
    """
    # Phase 1: Data Ingestion & Initial Extraction
    print("--- Phase 1: Data Ingestion & Initial Extraction ---")
    zerodha_articles = await scrape_zerodha_pulse()
    initial_events = []
    for article in zerodha_articles:
        text_to_process = f"{article['headline']}\n{article['summary']}"
        events = await extract_events(text_to_process)
        if events:
            initial_events.extend(events)

    print(f"Extracted {len(initial_events)} initial events from Zerodha Pulse.")

    # Phase 2: Event Enrichment and Deep Analysis
    print("\n--- Phase 2: Event Enrichment and Deep Analysis ---")
    brave_api_key = os.getenv("BRAVE_API_KEY")
    if not brave_api_key:
        raise ValueError("BRAVE_API_KEY not found.")
    brave_searcher = BraveNews(brave_api_key)

    all_enriched_text = []
    for event in initial_events:
        query = generate_brave_query(event)
        search_results = await brave_searcher.search_and_scrape(query, max_sources=3)
        if search_results:
            scraped_articles = await scrape_urls(search_results)
            for article in scraped_articles:
                if article.get('content'):
                    all_enriched_text.append(article['content'])

    print(f"Gathered enriched text from {len(all_enriched_text)} web pages.")

    consolidated_events = list(initial_events)
    if all_enriched_text:
        enriched_events = await extract_events("\n\n".join(all_enriched_text))
        if enriched_events:
            consolidated_events.extend(enriched_events)

    # Deduplicate events
    final_events = {event['event_name'].lower(): event for event in consolidated_events}.values()
    print(f"Consolidated to {len(final_events)} unique events.")

    # Phase 3: Knowledge Graph Population
    print("\n--- Phase 3: Knowledge Graph Population ---")
    if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
        print("Neo4j credentials not configured. Skipping graph population.")
        return

    importer = KnowledgeGraphImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    for event in final_events:
        importer.upsert_event(event)
    importer.close()
    print(f"Upserted {len(final_events)} events into Neo4j.")

if __name__ == '__main__':
    asyncio.run(run_financial_event_pipeline())