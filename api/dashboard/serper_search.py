# aigptssh/api/dashboard/serper_search.py
import requests
import os
from dotenv import load_dotenv
import asyncio
import re
from playwright.async_api import async_playwright
import pandas as pd
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from config import GPT4o_mini
from langchain_community.callbacks import get_openai_callback
from token_logger import log_token_usage
import aiohttp
import sys
from api.serper_searcher import SerperNews

# Load environment variables from .env file
load_dotenv()

class SerperDashboard:
    """
    A class to fetch financial data for the Indian market using the Serper News Search API,
    specifically tailored for a financial dashboard.
    """
    # Define specific queries for each data type
    def get_queries(self, country_name="India"):
        if country_name == "India":
            return {
                "latest_news": [
                    "latest Nifty 50 and Sensex news",
                    f"latest {country_name} economy news",
                    f"latest {country_name} corporate news"
                ],
                "standout_gainers": "top stock market gainers in India today",
                "standout_losers": "top stock market losers in India today"
            }
        elif country_name == "USA":
            return {
                "latest_news": [
                    "latest NASDAQ and S&P 500 news",
                    f"latest {country_name} economy news",
                    f"latest {country_name} corporate news"
                ],
                "standout_gainers": "top stock market gainers in USA today",
                "standout_losers": "top stock market losers in USA today"
            }
        else:
            return {
                "latest_news": [
                    f"latest {country_name} stock market news",
                    f"latest {country_name} economy news",
                    f"latest {country_name} corporate news"
                ],
                "standout_gainers": f"top stock market gainers in {country_name} today",
                "standout_losers": f"top stock market losers in {country_name} today"
            }


    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("SERPER_API_KEY")
        if not self.api_key:
            raise ValueError("Serper API key not provided or found in environment variables.")
        self.searcher = SerperNews(self.api_key)

    async def _get_reason_from_snippets_async(self, stock_name, search_results):
        """
        Uses an LLM to determine the reason for a stock's price movement from search result snippets.
        Now uses ainoke for non-blocking operation.
        """
        if not search_results:
            return {"reason": "Could not determine the reason from search results.", "source_url": ""}

        first_result = search_results[0]
        title = first_result.get("title", "")
        description = first_result.get("snippet", "")
        source_url = first_result.get("link", "")

        all_text = f"Title: {title}\nDescription: {description}"

        prompt = PromptTemplate(
            template="""
            Based on the following search snippets for '{stock_name}', what is the primary reason for its recent stock price movement?
            Provide a concise, one-sentence summary.

            Snippets:
            {snippets}

            Respond in a JSON format with two keys: "reason" and "source_url".
            """,
            input_variables=["stock_name", "snippets"],
        )

        parser = JsonOutputParser()
        chain = prompt | GPT4o_mini | parser

        try:
            with get_openai_callback() as cb:
                response = await chain.ainvoke({"stock_name": stock_name, "snippets": all_text})
                log_token_usage(
                    model_name=GPT4o_mini.model_name,
                    input_tokens=cb.prompt_tokens,
                    output_tokens=cb.completion_tokens,
                    total_tokens=cb.total_tokens,
                    purpose=f"trending_stock_reason_generation_for_{stock_name.replace(' ', '_')}"
                )
            response['source_url'] = source_url
            return response
        except Exception as e:
            print(f"LLM reason extraction failed for {stock_name}: {e}")
            return {"reason": "Could not summarize the reason.", "source_url": source_url}

    async def scrape_trending_stocks(self, country_code="IN"):
        """
        Asynchronously scrapes trending stocks based on the country code.
        - For "IN", scrapes StockEdge.
        - For "US", scrapes Business Insider.
        """
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        if country_code == "IN":
            return await self._scrape_trending_stocks_in()
        elif country_code == "US":
            return await self._scrape_trending_stocks_us()
        else:
            print(f"Trending stocks for country '{country_code}' not supported.")
            return {"trending_stocks": []}

    async def _scrape_trending_stocks_us(self):
        """
        Scrapes trending stocks for the US from CNBC Market Movers using precise selectors.
        """
        print("Scraping trending US stocks from CNBC...")
        url = "https://www.cnbc.com/us-market-movers/"
        trending_stocks = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_selector("section.MarketTop-fullWidthContainer", timeout=20000)

                print("Scraping Top Gainers...")
                gainers_section = page.locator("section.MarketTop-fullWidthContainer:has(h4:has-text('TOP GAINERS'))")
                gainer_rows = await gainers_section.locator("table.MarketTop-topTable tbody tr").all()

                for row in gainer_rows:
                    name_locator = row.locator("td.MarketTop-name a")
                    name = await name_locator.inner_text()

                    change_locator = row.locator("td.MarketTop-quoteGain")
                    percentage_change = await change_locator.inner_text()

                    trending_stocks.append({
                        "stock": name.strip(),
                        "percentage_change": f"+{percentage_change.strip()}",
                        "reason": "N/A",
                        "source": url
                    })

                print("Scraping Top Decliners...")
                losers_section = page.locator("section.MarketTop-fullWidthContainer:has(h4:has-text('TOP DECLINERS'))")
                loser_rows = await losers_section.locator("table.MarketTop-topTable tbody tr").all()

                for row in loser_rows:
                    name_locator = row.locator("td.MarketTop-name a")
                    name = await name_locator.inner_text()

                    change_locator = row.locator("td.MarketTop-quoteDecline")
                    percentage_change = await change_locator.inner_text()

                    trending_stocks.append({
                        "stock": name.strip(),
                        "percentage_change": f"-{percentage_change.strip()}",
                        "reason": "N/A",
                        "source": url
                    })

                print(f"Successfully scraped {len(trending_stocks)} market movers from CNBC.")

            except Exception as e:
                print(f"Error scraping CNBC Market Movers: {e}")
            finally:
                await browser.close()

        return {"trending_stocks": trending_stocks}


    async def _scrape_trending_stocks_in(self):
        """
        Asynchronously scrapes trending stocks for India from StockEdge using async playwright.
        """
        print("Scraping trending IN stocks from StockEdge...")

        base_url = "https://web.stockedge.com/trending-stocks?filter-type=Major%20Stocks"
        urls = {
            "Gainer": f"{base_url}&indicator=Gainers",
            "Loser": f"{base_url}&indicator=Losers"
        }

        trending_stocks = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for indicator, url in urls.items():
                await page.goto(url, timeout=60000)
                await page.wait_for_selector("div#in\\.stockedge\\.app\\:id\\/pricemovers-stockname-div")

                name_els = await page.query_selector_all("div#in\\.stockedge\\.app\\:id\\/pricemovers-stockname-div")
                change_selector = (
                    "ion-text#in\\.stockedge\\.app\\:id\\/pricemovers-stockchgpercentage-lbl-positive-txt, "
                    "ion-text#in\\.stockedge\\.app\\:id\\/pricemovers-stockchgpercentage-lbl-negative-txt"
                )
                change_els = await page.query_selector_all(change_selector)

                for name_el, change_el in zip(name_els, change_els):
                    stock_name = (await name_el.inner_text()).strip()
                    chg_text = (await change_el.inner_text()).strip()
                    chg_clean = chg_text.replace("▲", "").replace("▼", "").replace("%", "")

                    try:
                        chg_val = float(chg_clean)
                        if chg_val > 3:
                            reason_query = f"why is {stock_name} stock price {'increasing' if indicator == 'Gainer' else 'decreasing'} today"
                            async with aiohttp.ClientSession(**self.searcher.session_config) as session:
                                search_results = await self.searcher.search(session, reason_query, max_sources=3)
                            await asyncio.sleep(1)
                            reason_data = await self._get_reason_from_snippets_async(stock_name, search_results)

                            trending_stocks.append({
                                "stock": stock_name,
                                "percentage_change": f"+{chg_val}%" if indicator == "Gainer" else f"-{chg_val}%",
                                "reason": reason_data.get("reason", "Reason not found."),
                                "source": reason_data.get("source_url", "")
                            })
                    except ValueError:
                        continue

            await browser.close()

        return {"trending_stocks": trending_stocks}

    async def get_latest_news(self, queries, country_code, target_count=10):
        print(f"Fetching up to {target_count} latest news articles from Serper API for country {country_code}...")
        all_news_items = []
        urls_seen = set()
        
        async with aiohttp.ClientSession(**self.searcher.session_config) as session:
            for query in queries:
                results = await self.searcher.search(session, query, search_type='news', max_sources=target_count, country=country_code, freshness='pd')
                if not results:
                    print(f"No news results found for query: '{query}'")
                    continue

                for item in results:
                    url = item.get("link")
                    if url and url not in urls_seen:
                        urls_seen.add(url)
                        all_news_items.append({
                            "title": item.get("title"),
                            "url": url,
                            "description": item.get("snippet"),
                            "page_age": item.get("publication_date"),
                            "age": item.get("date")
                        })
        
        print(f"Successfully fetched {len(all_news_items)} unique news articles for {country_code}.")
        return all_news_items

    async def get_portfolio_data(self, portfolio: list[str]):
        print(f"Fetching data for portfolio: {portfolio}")
        all_news = []
        urls_seen = set()
        async with aiohttp.ClientSession(**self.searcher.session_config) as session:
            for stock in portfolio:
                query = f"{stock} stock news"
                results = await self.searcher.search(session, query, search_type='news', max_sources=10)
                if results:
                    for item in results:
                        url = item.get("link")
                        if url and url not in urls_seen:
                            urls_seen.add(url)
                            all_news.append({
                                "title": item.get("title"),
                                "url": url,
                                "description": item.get("snippet"),
                                "page_age": item.get("publication_date"),
                                "age": item.get("date")
                            })
                await asyncio.sleep(1)
        return {"latest_news": all_news}

    async def get_dashboard_data(self, country_code="IN", country_name="India"):
        """
        Fetches dashboard data for a specific country.
        """
        print(f"Starting data acquisition for {country_name} from Serper API...")
        queries = self.get_queries(country_name)
        news = await self.get_latest_news(queries["latest_news"], country_code, target_count=10)
        dashboard_data = {
            "latest_news": news,
        }
        print(f"Serper API data acquisition for {country_name} complete.")
        return dashboard_data