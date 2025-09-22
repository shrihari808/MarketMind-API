# api/graph/data_ingestion.py
import asyncio
import os
from dotenv import load_dotenv
from transformers import pipeline
import aiohttp
from langchain.text_splitter import RecursiveCharacterTextSplitter

from api.brave_searcher import BraveNews
from api.dashboard.web_scraper import scrape_urls

load_dotenv()

def generate_search_queries(company_name: str) -> list[str]:
    """Generates a list of targeted search queries for a given company."""
    return [
        # Company–Event Relations
        f'"{company_name}" acquisition OR merger',
        f'"{company_name}" partnership OR collaboration',
        f'"{company_name}" lawsuit OR legal action',
        f'"{company_name}" management changes OR CEO appointment',

        # Company–Financial Relations
        f'"{company_name}" earnings OR revenue OR profit',
        f'"{company_name}" stock movement OR shares rose OR shares fell',
        f'"{company_name}" analyst forecast OR price target',
        f'"{company_name}" dividend announcement',

        # Company–Market/Industry Relations
        f'"{company_name}" competitor OR challenges',
        f'"{company_name}" market trend OR sector news',
        f'"{company_name}" regulation OR policy impact',

        # Company–Geopolitical/External Factors
        f'"{company_name}" expands operations in OR exits from',
        f'"{company_name}" sanctions OR trade restrictions',
        f'"{company_name}" supply chain disruption OR natural disaster impact',

        # Company–Sentiment / Opinion Relations
        f'"{company_name}" analyst rating OR analyst opinion',
        f'"{company_name}" media sentiment OR public reaction',

        # Supply Chain / Operational Relations
        f'"{company_name}" supplier OR raw material provider',
        f'"{company_name}" distributor OR retail partner',
        f'"{company_name}" production halt OR factory closure',
    ]

async def get_relevant_text(company_name: str) -> list[str]:
    """
    Fetches, scrapes, and pre-filters text content for a given company.
    """
    # 1. Intelligent Search Query Generation
    queries = generate_search_queries(company_name)

    # 2. Brave Search for URLs
    brave_api_key = os.getenv("BRAVE_API_KEY")
    if not brave_api_key:
        raise ValueError("BRAVE_API_KEY not found in environment variables.")
    
    brave_search = BraveNews(brave_api_key)
    
    all_articles = []
    async with aiohttp.ClientSession(**brave_search.session_config) as session:
        for query in queries:
            # --- THIS IS THE CHANGE: Fetching more sources per query ---
            articles = await brave_search.search_and_scrape(session, query, max_pages=1, max_sources=10)
            if articles:
                all_articles.extend(articles)

    unique_urls = {article['link']: article for article in all_articles if 'link' in article}.values()
    urls_to_scrape = [{'url': article['link']} for article in unique_urls]

    # 3. Web Scraping
    print(f"\nScraping content from {len(urls_to_scrape)} unique URLs...")
    scraped_articles = await scrape_urls(urls_to_scrape)
    scraped_content = [article.get('content', '') for article in scraped_articles if article.get('content')]

    # 4. Pre-filtering with FinBERT
    print("\nFiltering relevant content with FinBERT...")
    finbert = pipeline("sentiment-analysis", model="ProsusAI/finbert", top_k=1)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    
    financially_relevant_texts = []
    
    for content in scraped_content:
        if not content or not isinstance(content, str):
            continue

        try:
            chunks = text_splitter.split_text(content)
            is_relevant_document = False
            
            for chunk in chunks:
                results = finbert(chunk)
                top_result = results[0][0]
                
                if top_result['label'] in ['positive', 'negative', 'neutral'] and top_result['score'] > 0.85:
                    is_relevant_document = True
                    break
            
            if is_relevant_document:
                financially_relevant_texts.append(content)
                print(f"  - Document classified as RELEVANT.")
            else:
                print(f"  - Document classified as IRRELEVANT.")

        except Exception as e:
            print(f"  - Could not process document with FinBERT. Error: {e}")
            continue

    return financially_relevant_texts

if __name__ == '__main__':
    async def main():
        company = "Reliance Industries"
        relevant_texts = await get_relevant_text(company)
        print(f"\nFound {len(relevant_texts)} financially relevant articles.")
        if relevant_texts:
            print("\n--- Sample of first relevant article ---")
            print(relevant_texts[0][:1000] + "...")
            print("-" * 40)
    
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())