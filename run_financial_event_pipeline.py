# aigptssh/run_financial_event_pipeline.py
import asyncio
from api.graph.zerodha_scraper import scrape_zerodha_pulse
from api.graph.event_extractor import extract_events
from api.graph.neo4j_importer import KnowledgeGraphImporter, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
import os

async def run_financial_event_pipeline():
    """
    Orchestrates the entire financial event knowledge graph pipeline,
    processing articles in batches for efficiency.
    """
    # Phase 1: Data Ingestion
    print("--- Phase 1: Data Ingestion ---")
    zerodha_articles = await scrape_zerodha_pulse()
    if not zerodha_articles:
        print("No articles found to process. Exiting.")
        return

    print(f"Successfully scraped {len(zerodha_articles)} articles.")

    # Phase 2: Batch Event Extraction
    print("\n--- Phase 2: Batch Event Extraction ---")
    
    # Combine the text of all articles into a single string for batch processing
    full_text_corpus = "\n\n---\n\n".join([f"{article['headline']}\n{article['summary']}" for article in zerodha_articles])
    
    # Process the entire corpus in one go
    all_events = await extract_events(full_text_corpus)

    if not all_events:
        print("No events could be extracted from the articles. Exiting.")
        return
        
    print(f"Extracted a total of {len(all_events)} events from all articles.")

    # Phase 3: Knowledge Graph Population
    print("\n--- Phase 3: Knowledge Graph Population ---")
    if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
        print("Neo4j credentials not configured. Skipping graph population.")
        return

    importer = KnowledgeGraphImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    for event in all_events:
        # Ensure the event is a dictionary before trying to upsert it
        if isinstance(event, dict):
            importer.upsert_event(event)
        else:
            print(f"Skipping malformed event: {event}")

    importer.close()
    print(f"Upserted {len(all_events)} events into Neo4j.")

if __name__ == '__main__':
    # This ensures the script can run on Windows without asyncio errors
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_financial_event_pipeline())