# /aigptssh/api/serper_searcher.py
import os
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

class SerperNews:
    """
    A class to fetch financial data using the Serper API.
    """
    SERPER_API_BASE_URL = "https://google.serper.dev/news"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Serper API key is required.")
        self.api_key = api_key
        self.headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        self.session_config = {
            'timeout': aiohttp.ClientTimeout(total=10),
            'connector': aiohttp.TCPConnector(limit=5),
        }

    async def search_and_scrape(self, session: aiohttp.ClientSession, query: str, **kwargs) -> list:
        """
        Performs a search using the Serper API and returns a list of articles.
        The 'scrape' part is now just returning the structured data from Serper.
        """
        payload = {
            "q": query,
            "num": kwargs.get("max_sources", 10),
        }
        try:
            async with session.post(self.SERPER_API_BASE_URL, headers=self.headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = []
                    for item in data.get("news", []):
                        articles.append({
                            "title": item.get("title"),
                            "link": item.get("link"),
                            "snippet": item.get("snippet"),
                            "publication_date": item.get("date"),
                            "source": item.get("source"),
                        })
                    return articles
                else:
                    print(f"Serper API Error: {response.status} - {await response.text()}")
                    return []
        except Exception as e:
            print(f"Error during Serper API request: {e}")
            return []