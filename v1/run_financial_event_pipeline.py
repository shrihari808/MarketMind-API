# aigptssh/run_financial_event_pipeline.py
import asyncio
import os
from api.graph.zerodha_scraper import scrape_zerodha_pulse
from api.graph.event_extractor import extract_events, generate_brave_query
from api.news_rag.scoring_service import calculate_impact_score
from api.brave_searcher import BraveNews
from api.dashboard.web_scraper import scrape_urls
from api.graph.neo4j_importer import KnowledgeGraphImporter as EventKnowledgeGraphImporter, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from run_pipeline import run_full_pipeline # Import the original pipeline
from import_graph import KnowledgeGraphImporter
import aiohttp
import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Initialize the Gemini Flash model for company extraction
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)

async def get_impacted_companies_from_llm(search_results: list[dict]) -> list[str]:
    """
    Uses an LLM to extract impacted company names from a list of search result snippets.
    """
    if not search_results:
        return []

    # Combine titles and snippets into a single context string
    context = "\n".join([f"Title: {result.get('title', '')}\nSnippet: {result.get('snippet', '')}" for result in search_results])
    
    parser = JsonOutputParser()
    prompt = ChatPromptTemplate.from_template(
        """
        You are an expert financial analyst. From the following news snippets, identify up to 3 unique and relevant Indian companies that are mentioned as being impacted.
        
        **CRITICAL INSTRUCTIONS:**
        - Only extract the names of the companies.
        - Do not extract sectors, indices, or general market terms.
        - Return a JSON object with a single key "companies" which is a list of the company names.
        - If no specific companies are mentioned, return an empty list.

        **Snippets:**
        {context}

        {format_instructions}
        """,
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    
    chain = prompt | llm | parser
    
    try:
        response = await chain.ainvoke({"context": context})
        if isinstance(response, dict) and "companies" in response and isinstance(response["companies"], list):
            # Clean up names to remove extra descriptions
            cleaned_companies = [re.sub(r'\s+\(.*?\)|\'s.*', '', company).strip() for company in response["companies"]]
            return list(set(cleaned_companies))[:3] # Return unique names, capped at 3
        return []
    except Exception as e:
        print(f"Error during LLM-based company extraction: {e}")
        return []

async def run_financial_event_pipeline():
    """
    Orchestrates the entire financial event knowledge graph pipeline,
    from data ingestion to knowledge graph population, including event prioritization
    and data enhancement via secondary web searches.
    """
    brave_api_key = os.getenv("BRAVE_API_KEY")
    if not brave_api_key:
        print("Brave API key not found. Skipping enhancement.")
        return

    searcher = BraveNews(brave_api_key)

    async with aiohttp.ClientSession(**searcher.session_config) as session:
        # --- Phase 1: Data Ingestion and Initial Processing ---
        print("--- Phase 1: Data Ingestion and Initial Processing ---")
        
        # 1. Scrape Zerodha Pulse for initial articles
        print("\n[Step 1.1] Scraping initial articles from Zerodha Pulse...")
        initial_articles = await scrape_zerodha_pulse()
        if not initial_articles:
            print("No articles found from Zerodha Pulse. Exiting pipeline.")
            return

        print(f"Scraped {len(initial_articles)} initial articles.")

        # 2. Extract all events from the initial articles
        print("\n[Step 1.2] Extracting all potential events from scraped articles...")
        combined_text = "\n\n---\n\n".join([f"{article['headline']}\n{article['summary']}" for article in initial_articles])
        all_events = await extract_events(combined_text)

        if not all_events:
            print("No events could be extracted. Exiting pipeline.")
            return
        print(f"Extracted {len(all_events)} total potential events.")

        # --- Phase 2: Event Prioritization and Enhancement ---
        print("\n--- Phase 2: Event Prioritization and Enhancement ---")

        # 1. Identify most important events by scoring them
        print("\n[Step 2.1] Scoring and prioritizing events...")
        for event in all_events:
            event['impact_score'] = calculate_impact_score(event, source_credibility=0.8) # Zerodha Pulse is a credible source

        # Sort events by impact score in descending order
        prioritized_events = sorted(all_events, key=lambda x: x.get('impact_score', 0), reverse=True)
        
        # Select the top N events to enhance (e.g., top 5)
        top_events = prioritized_events[:5]
        print(f"Prioritized the top {len(top_events)} events for enhancement.")

        # 2. Generate and execute Brave search queries for top events
        print("\n[Step 2.2] Generating and executing Brave Search queries for top events...")
        urls_to_scrape_for_enhancement = []
        for event in top_events:
            # Generate multiple queries for broader context
            queries = generate_brave_query(event)
            event['enhancement_urls'] = []
            for query in queries:
                # Search for a few highly relevant sources for each query type
                search_results = await searcher.search_and_scrape(session, query, max_pages=1, max_sources=2) # 2 sources per query
                if search_results:
                    # Associate the found URLs with the event for later processing
                    urls_for_query = [res['link'] for res in search_results if 'link' in res]
                    event['enhancement_urls'].extend(urls_for_query)
            
            urls_to_scrape_for_enhancement.extend(event.get('enhancement_urls', []))
        
        print(f"Found {len(urls_to_scrape_for_enhancement)} URLs for deep data extraction across all queries.")

        # --- Phase 3: Deep Data Extraction and Knowledge Graph Integration ---
        print("\n--- Phase 3: Deep Data Extraction and Knowledge Graph Integration ---")

        # 1. Scrape URLs from Brave Search
        print("\n[Step 3.1] Scraping full content from enhancement URLs...")
        # We need to pass the URLs in the format scrape_urls expects
        url_dicts_to_scrape = [{'url': url} for url in set(urls_to_scrape_for_enhancement)]
        scraped_enhancement_articles = await scrape_urls(url_dicts_to_scrape)
        
        url_content_map = {article['url']: article.get('content', '') for article in scraped_enhancement_articles}

        # 2. Enhance Knowledge Graph Information
        print("\n[Step 3.2] Re-extracting events from detailed content to enhance data...")
        enhanced_events_data = []
        for event in top_events:
            full_content_for_event = []
            for url in event.get('enhancement_urls', []):
                content = url_content_map.get(url)
                if content:
                    full_content_for_event.append(content)
            
            if full_content_for_event:
                combined_enhancement_text = "\n\n---\n\n".join(full_content_for_event)
                # Re-run extraction on the detailed text
                extracted_details_list = await extract_events(combined_enhancement_text)
                
                if extracted_details_list:
                    # For simplicity, we'll merge the first and most detailed extraction
                    # with the original event. A more complex strategy could merge all details.
                    primary_detail = extracted_details_list[0]
                    
                    # Merge details: update original event with new, richer info
                    event['summary'] = primary_detail.get('summary', event['summary'])
                    event['amount'] = primary_detail.get('amount', event['amount'])
                    # You can add more complex merging logic here
                    
                    print(f"Enhanced event: {event['event_name']}")

            enhanced_events_data.append(event)

        # 3. Upsert into Knowledge Graph
        print("\n[Step 3.3] Upserting enhanced event data into Neo4j Knowledge Graph...")
        if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
            print("Neo4j credentials not configured. Skipping graph population.")
        else:
            importer = EventKnowledgeGraphImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
            # Upsert the top, enhanced events. You could also upsert the remaining prioritized_events.
            for event in enhanced_events_data:
                if isinstance(event, dict):
                    importer.upsert_event(event)
            
            importer.close()
            print(f"Upserted {len(enhanced_events_data)} enhanced events into Neo4j.")

        # --- Phase 4: Expanded Pipeline ---
        print("\n--- Phase 4: Expanded Pipeline ---")
        
        # 1. Identify impacted sectors from the knowledge graph
        print("\n[Step 4.1] Identifying impacted sectors from the knowledge graph...")
        importer = EventKnowledgeGraphImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        impacted_sectors = []
        for event in top_events:
            sectors = importer.get_impacted_sectors(event['event_name'])
            impacted_sectors.extend(sectors)
        
        impacted_sectors = list(set(impacted_sectors))
        print(f"Identified impacted sectors: {impacted_sectors}")
        
        # 2. Ingest more news about the impacted sectors
        print("\n[Step 4.2] Ingesting more news about the impacted sectors...")
        sector_search_results = []
        for sector in impacted_sectors:
            query = f"{sector} sector news India"
            search_results = await searcher.search_and_scrape(session, query, max_pages=1, max_sources=5)
            if search_results:
                sector_search_results.extend(search_results)

        print(f"Found {len(sector_search_results)} articles for sector-specific news.")
        
        # 3. Conduct a broad search and use LLM to find impacted stocks
        print("\n[Step 4.3] Identifying impacted stocks using LLM...")
        impacted_companies = await get_impacted_companies_from_llm(sector_search_results)
        print(f"Identified impacted companies: {impacted_companies}")
        
        # 4. Run the general knowledge graph pipeline for each identified company
        print("\n[Step 4.4] Running the general knowledge graph pipeline for each identified company...")
        graph_importer = KnowledgeGraphImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        for company in impacted_companies:
            output_data = await run_full_pipeline(company)
            if output_data:
                graph_importer.import_graph(output_data)
                print(f"Successfully upserted data for {company} into the knowledge graph.")
        graph_importer.close()

    print("\n--- Financial Event Pipeline Completed Successfully ---")


if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_financial_event_pipeline())