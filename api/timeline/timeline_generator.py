# aigptssh/api/timeline/timeline_generator.py
import os
import json
import asyncio
from datetime import datetime, timezone

# Adjusting import paths based on project structure
import sys
# Add the project root to the Python path to allow for absolute imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from api.dashboard.brave_search import BraveDashboard
from api.dashboard.data_aggregator import select_latest_news_articles

# --- Define Paths ---
TIMELINE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(TIMELINE_DIR, 'timeline.json')

async def generate_timeline():
    """
    Fetches the latest financial news, processes it, and saves it to a JSON file.
    This function is intended to be called by a scheduler.
    """
    print("--- Starting Timeline Generation ---")

    try:
        brave_fetcher = BraveDashboard()

        # Define queries to get a broad range of important news
        queries = {
            "indices": "latest stock market indices news india",
            "trending": "trending stocks today india",
            "major_financial": "major financial news india past day"
        }

        # Fetch articles for all queries concurrently
        print("Fetching news articles from Brave Search API...")
        search_tasks = [
            brave_fetcher.get_latest_news(query, "IN", target_count=15)
            for query in queries.values()
        ]
        results_list = await asyncio.gather(*search_tasks)

        # Combine and deduplicate articles
        all_articles = {}
        for articles in results_list:
            for article in articles:
                if article.get('url'):
                    all_articles[article['url']] = article
        
        unique_articles = list(all_articles.values())
        print(f"Found {len(unique_articles)} unique articles.")

        # Format and select the latest articles
        # The select_latest_news_articles function sorts by age and formats the output
        if not unique_articles:
            print("No articles found. Timeline will not be updated.")
            return

        # Select a larger number of articles for the timeline, e.g., 30
        timeline_articles = select_latest_news_articles(unique_articles, count=30)

        # Prepare the final JSON structure
        timeline_data = {
            "last_updated_utc": datetime.now(timezone.utc).isoformat(),
            "timeline_items": timeline_articles
        }

        # Save the data to the JSON file
        print(f"Saving timeline data to {OUTPUT_PATH}...")
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, indent=4, ensure_ascii=False)

        print("--- Timeline Generation Complete ---")

    except Exception as e:
        print(f"An error occurred during timeline generation: {e}")

if __name__ == '__main__':
    # This allows running the script directly for testing
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(generate_timeline())
