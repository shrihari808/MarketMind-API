# /aigptssh/streaming/reddit_stream.py

import os
import json
import asyncio
import aiohttp
from langchain import PromptTemplate, LLMChain
from langchain_community.chat_message_histories import (
    PostgresChatMessageHistory,
)
from fastapi import FastAPI, HTTPException
import requests
import re
from urllib.parse import urlparse
import asyncpg
import pandas as pd
from fastapi.responses import StreamingResponse
from openai import OpenAI
import pandas as pd
from config import DB_POOL
from api.serper_searcher import SerperNews
from api.reddit_scraper import RedditScraper
from api.reddit_rag.reddit_vector_store import create_reddit_vector_store_from_scraped_data


from dotenv import load_dotenv
load_dotenv(override=True)

pg_ip=os.getenv('PG_IP_ADDRESS')
psql_url=os.getenv('DATABASE_URL')



async def fetch_search_red(query: str, serper_api_key: str):
    searcher = SerperNews(serper_api_key)
    # Use the search method with a site-specific query
    async with aiohttp.ClientSession(**searcher.session_config) as session:
        results = await searcher.search(session, f"site:reddit.com {query}", search_type='search')
    return results


async def process_search_red(search_results: list[dict]):
    if not search_results:
        print("DEBUG: process_search_red received no search results.")
        return None, None, None

    articles = []
    links = []
    # --- ADD THIS SNIPPET ---
    for item in search_results:
        articles.append({
            "title": item.get("title", ""),
            "description": item.get("snippet", ""),
            "url": item.get("link"),
            "page_age": item.get("publication_date")
        })
        links.append(item.get('link'))
    # --- END OF SNIPPET ---

    print(f"DEBUG: Processed {len(articles)} articles and {len(links)} links from search results.")

    # Create a DataFrame for potential database insertion
    df = pd.DataFrame(articles)

    return articles, df, links


async def insert_red(db):
    df = db
    if not DB_POOL:
        print("ERROR: Database pool not initialized.")
        return

    try:
        async with DB_POOL.acquire() as conn:
            for index, row in df.iterrows():
                source_url = row['source_url']
                image_url = None
                heading = None
                title = row['title']
                description = row['description']
                source_date = row['source_date']

                # Check if the row already exists
                exists = await conn.fetchval(
                    "SELECT 1 FROM source_data WHERE source_url = $1", source_url
                )
                if not exists:
                    # Prepare and execute the SQL query
                    insert_query = """
                        INSERT INTO source_data (source_url, image_url, heading, title, description, source_date)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """
                    await conn.execute(insert_query, source_url, image_url, heading, title, description, source_date)

    except Exception as e:
        print(f"Error in insert_red: {e}")