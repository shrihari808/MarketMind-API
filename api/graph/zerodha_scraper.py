# aigptssh/api/graph/zerodha_scraper.py
import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def scrape_zerodha_pulse():
    """
    Fetches the latest news articles by scraping the Zerodha Pulse HTML page.
    This method is updated to handle HTML parsing instead of expecting a JSON API response.
    """
    articles = []
    # The target URL is the main page, which renders the news articles.
    page_url = "https://pulse.zerodha.com/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    print("\n--- [DEBUG] Starting HTML Scraper for Zerodha Pulse ---")
    print(f"[DEBUG] Target Page URL: {page_url}")

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(page_url, timeout=15) as response:
                response.raise_for_status()
                # The response is HTML, so we read the text content.
                html_content = await response.text()
                
                # Use BeautifulSoup to parse the HTML.
                soup = BeautifulSoup(html_content, "html.parser")
                
                # Find the main container for the news articles.
                news_list = soup.find('ul', id='news')
                if not news_list:
                    print("[DEBUG] Could not find the news list container ('ul' with id='news').")
                    return []

                # Find all individual news items.
                news_items = news_list.find_all('li', class_='item')
                print(f"[DEBUG] Found {len(news_items)} news items on the page.")

                for item in news_items:
                    title_element = item.find('h2', class_='title')
                    desc_element = item.find('div', class_='desc')
                    
                    if title_element and title_element.a:
                        headline = title_element.a.get_text(strip=True)
                        url = title_element.a['href']
                        summary = desc_element.get_text(strip=True) if desc_element else ""

                        articles.append({
                            "headline": headline,
                            "summary": summary,
                            "url": url
                        })

    except aiohttp.ClientError as e:
        print(f"FATAL ERROR [aiohttp]: Network request to the page failed. Details: {e}")
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