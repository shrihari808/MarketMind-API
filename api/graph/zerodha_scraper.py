# aigptssh/api/graph/zerodha_scraper.py
import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def scrape_zerodha_pulse():
    """
    Fetches the latest news articles directly from the Zerodha Pulse WordPress API.
    This is the most reliable method as it avoids HTML scraping and browser automation.
    """
    articles = []
    # This is the official API endpoint the website uses to load its articles.
    api_url = "https://pulse.zerodha.com/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    print("\n--- [DEBUG] Starting Direct API Scraper ---")
    print(f"[DEBUG] Target API URL: {api_url}")

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(api_url, timeout=15) as response:
                response.raise_for_status()
                # The response is in JSON format, so we parse it directly
                posts = await response.json()
                print(f"[DEBUG] Successfully fetched {len(posts)} articles from the API.")

                for post in posts:
                    # Extract the headline from the 'title' object
                    headline = post.get('title', {}).get('rendered', '')
                    
                    # The summary is in the 'excerpt' object and contains HTML tags, 
                    # so we use BeautifulSoup to clean them out.
                    raw_summary = post.get('excerpt', {}).get('rendered', '')
                    summary = BeautifulSoup(raw_summary, "html.parser").get_text(strip=True)

                    # Extract the direct URL to the article
                    url = post.get('link', '')

                    if headline and url:
                        articles.append({
                            "headline": headline,
                            "summary": summary,
                            "url": url
                        })

    except aiohttp.ClientError as e:
        print(f"FATAL ERROR [aiohttp]: Network request to API failed. Details: {e}")
    except Exception as e:
        print(f"FATAL ERROR [General]: An unexpected error occurred. Details: {e}")

    print(f"--- [DEBUG] Scraper Finished. Total Articles Found: {len(articles)} ---")
    return articles

if __name__ == '__main__':
    async def main():
        scraped_articles = await scrape_zerodha_pulse()
        print(f"\n--- SCRAPER TEST COMPLETE ---")
        print(f"Scraped {len(scraped_articles)} articles from Zerodha Pulse.")
        if scraped_articles:
            for i, article in enumerate(scraped_articles[:3]):
                print(f"\n--- Article {i+1} ---")
                print(f"Headline: {article['headline']}")
                print(f"Summary: {article['summary']}")
                print(f"URL: {article['url']}")

    asyncio.run(main())