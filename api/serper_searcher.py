# /aigptssh/api/serper_searcher.py
import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from datetime import datetime, timedelta
import re

load_dotenv()

def parse_flexible_date(date_string: str) -> str:
    """
    Parse various date formats from Serper API and return ISO format.
    Handles: "2 days ago", "Dec 19, 2024", "24 Sept 2025", etc.
    """
    if not date_string:
        return datetime.now().strftime("%Y-%m-%d")

    date_string = date_string.strip()

    # Handle relative dates like "2 days ago", "1 hour ago", etc.
    relative_pattern = r'(\d+)\s+(day|hour|minute|week|month)s?\s+ago'
    match = re.match(relative_pattern, date_string, re.IGNORECASE)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()

        if unit == 'minute':
            delta = timedelta(minutes=amount)
        elif unit == 'hour':
            delta = timedelta(hours=amount)
        elif unit == 'day':
            delta = timedelta(days=amount)
        elif unit == 'week':
            delta = timedelta(weeks=amount)
        elif unit == 'month':
            delta = timedelta(days=amount * 30) # Approximation
        else:
            delta = timedelta(days=0)

        return (datetime.now() - delta).strftime("%Y-%m-%d")

    # Try various absolute date formats
    date_formats = [
        "%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y",
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"
    ]

    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_string, fmt)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    print(f"WARNING: Could not parse date string: '{date_string}', using current date")
    return datetime.now().strftime("%Y-%m-%d")


class SerperNews:
    """
    A class to fetch financial data using the Serper API.
    """
    SERPER_API_BASE_URL = "https://google.serper.dev/"

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

    async def search(self, session: aiohttp.ClientSession, query: str, search_type: str = 'search', **kwargs) -> list:
        """
        Performs a search using the Serper API.
        """
        endpoint = "news" if search_type == "news" else "search"
        url = f"{self.SERPER_API_BASE_URL}{endpoint}"

        payload = {
            "q": query,
            "num": kwargs.get("max_sources", 10),
        }
        try:
            async with session.post(url, headers=self.headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = []
                    results = data.get("news", []) if search_type == "news" else data.get("organic", [])

                    for item in results:
                        articles.append({
                            "title": item.get("title"),
                            "link": item.get("link"),
                            "snippet": item.get("snippet"),
                            "publication_date": parse_flexible_date(item.get("date")),
                            "source": item.get("source"),
                        })
                    return articles
                else:
                    print(f"Serper API Error: {response.status} - {await response.text()}")
                    return []
        except Exception as e:
            print(f"Error during Serper API request: {e}")
            return []