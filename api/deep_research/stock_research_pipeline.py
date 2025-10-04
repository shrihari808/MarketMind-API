# /aigptssh/api/deep_research/stock_research_pipeline.py

import asyncio
import os
from datetime import datetime
from io import BytesIO
import json
import time

import aiohttp
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, PageBreak
from langchain_google_genai import ChatGoogleGenerativeAI

from api.brave_searcher import BraveNews
from api.dashboard.web_scraper import scrape_urls
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

# Initialize both Gemini models for specialized tasks
llm_pro = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.1)
llm_flash = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)


class StockResearchPipeline:
    """
    A multi-step, parallel pipeline to generate a comprehensive stock research report.
    This version uses Gemini Flash for lighter tasks and Gemini Pro for content generation.
    """

    def __init__(self, company_name: str):
        self.company_name = company_name
        self.brave_searcher = BraveNews(os.getenv("BRAVE_API_KEY"))
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.report_sections = [
            "Executive Summary", "Key Highlights & Events", "Fundamental Analysis",
            "Technical Analysis", "Price Movements & Event Impact", "Brokerage & Analyst Views",
            "Sector & Peer Comparison", "News & Developments", "Macroeconomic & Geopolitical Factors",
            "Risks & Red Flags", "Scenarios & Valuation Outlook", "Final Recommendation"
        ]

    async def run(self):
        """
        Orchestrates the entire process of data gathering, analysis, and report generation.
        """
        start_time = time.time()
        print(f"[{datetime.now()}] --- Starting Advanced Stock Analysis for: {self.company_name} ---")
        
        # Use a single session with a very long timeout
        timeout = aiohttp.ClientTimeout(total=300) # 5-minute timeout for network requests
        async with aiohttp.ClientSession(**self.brave_searcher.session_config, timeout=timeout) as session:
            
            # 1. Dynamically generate search queries for each report section
            print(f"\n[{datetime.now()}] [Step 1/5] Generating targeted search queries using Gemini Flash...")
            queries = await self._generate_search_queries()
            print(f"[{datetime.now()}] Generated {len(queries)} queries.")
            
            # 2. Gather all data concurrently with rate limiting
            print(f"\n[{datetime.now()}] [Step 2/5] Gathering data from {len(queries)} web sources...")
            scraped_content = await self._gather_data(session, queries)
            print(f"[{datetime.now()}] Gathered and scraped content: {len(scraped_content)} characters.")
            
            # 3. Route content to relevant sections
            print(f"\n[{datetime.now()}] [Step 3/5] Routing context to analysis sections using Gemini Flash...")
            routed_context = await self._route_content(scraped_content)
            
            # 4. Generate each report section in parallel
            print(f"\n[{datetime.now()}] [Step 4/5] Generating all 12 report sections in parallel using Gemini Pro...")
            generation_tasks = [
                self._generate_section(section, routed_context.get(section, ""))
                for section in self.report_sections
            ]
            report_parts = await asyncio.gather(*generation_tasks)
            
            final_report_text = "\n\n".join(report_parts)
            if not final_report_text.strip():
                print("Error: LLM failed to generate report sections.")
                return None
            print(f"[{datetime.now()}] All sections generated. Total report length: {len(final_report_text)} characters.")
        
        # 5. Create the PDF
        print(f"\n[{datetime.now()}] [Step 5/5] Assembling and creating the final PDF report...")
        pdf_buffer = self._create_pdf_from_text(final_report_text)
        
        end_time = time.time()
        print(f"\n[{datetime.now()}] --- Stock Research Pipeline Completed Successfully in {end_time - start_time:.2f} seconds ---")
        return pdf_buffer

    async def _generate_search_queries(self) -> list:
        """Uses Gemini Flash to create a list of specific search queries."""
        parser = JsonOutputParser()
        prompt = ChatPromptTemplate.from_template(
            """
            For the company "{company_name}", generate a JSON list of 15 highly specific Brave search queries to gather data for a comprehensive financial research report. The queries should cover:
            1.  **Fundamentals**: P/E, EV/EBITDA, Debt/Equity, ROE, Revenue Growth, EPS.
            2.  **Technicals**: RSI, MACD, 50-day SMA, Support & Resistance levels.
            3.  **News & Events**: Latest earnings calls, M&A, partnerships.
            4.  **Analyst Views**: Consensus rating, price target upgrades/downgrades.
            5.  **Peer Comparison**: Top competitors, sector performance.
            6.  **Risks & Macro Factors**: Geopolitical risks, supply chain issues, regulatory changes.
            
            Return a JSON object with a single key "queries" containing the list of strings.
            {format_instructions}
            """,
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = prompt | llm_flash | parser
        result = await chain.ainvoke({"company_name": self.company_name})
        return result.get("queries", [])

    async def _gather_data(self, session: aiohttp.ClientSession, queries: list) -> str:
        """Executes search queries with rate limiting and retries, scrapes URLs, and returns all content."""
        semaphore = asyncio.Semaphore(1)  # Limit to 1 concurrent request per second
        tasks = []

        async def fetch_with_semaphore(query):
            async with semaphore:
                for attempt in range(3): # Retry up to 3 times
                    try:
                        result = await self.brave_searcher.search_and_scrape(session, query, max_sources=2)
                        await asyncio.sleep(1.1)  # Wait 1.1 seconds between requests
                        return result
                    except Exception as e:
                        print(f"Brave search failed for query '{query}' (attempt {attempt + 1}): {e}. Retrying...")
                        await asyncio.sleep(2 ** attempt) # Exponential backoff
                return []

        for query in queries:
            tasks.append(fetch_with_semaphore(query))
        
        results = await asyncio.gather(*tasks)
        all_articles = [article for result in results for article in result]
        unique_urls = {article["link"]: article for article in all_articles if article.get("link")}.values()
        
        if not unique_urls:
            return ""
            
        scraped_articles = await scrape_urls(list(unique_urls))
        return json.dumps([
            {"url": article.get('url', ''), "title": article.get('title', ''), "content": article.get('content', '')}
            for article in scraped_articles if article.get("content")
        ])

    async def _route_content(self, scraped_content_json: str) -> dict:
        """Uses Gemini Flash to route scraped content to the appropriate report sections."""
        parser = JsonOutputParser()
        prompt = ChatPromptTemplate.from_template(
            """
            You are a content routing expert. Your job is to categorize scraped web content into the most relevant sections of a financial report for "{company_name}".
            
            The report sections are: {sections}
            
            Here is the scraped content (character count: {char_count}):
            {scraped_content}
            
            Return a JSON object where each key is a report section, and the value is a string concatenating the content relevant to that section.
            {format_instructions}
            """,
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = prompt | llm_flash | parser
        return await chain.ainvoke({
            "company_name": self.company_name,
            "sections": ", ".join(self.report_sections),
            "scraped_content": scraped_content_json,
            "char_count": len(scraped_content_json)
        })
        
    async def _generate_section(self, section_name: str, context: str) -> str:
        """Generates the content for a single report section using Gemini Pro with a long timeout."""
        if not context:
            return f"## {section_name}\n\nData not available in the provided sources for this section."
            
        system_prompt = f"""
        You are a financial analyst AI writing the "{section_name}" section of a research report for {self.company_name} on {self.today}.
        Your analysis must be based ONLY on the provided context.
        If the context is insufficient, state that data was not available.
        Use markdown for formatting. Be structured, evidence-based, and investment-grade.
        """
        
        human_prompt = """
        **Context for your section (character count: {char_count}):**
        {context}

        ---
        **ANALYSIS FRAMEWORK for the "{section_name}" section:**
        {framework}
        
        ---
        Now, write the "{section_name}" section of the report.
        """
        
        frameworks = {
            "Executive Summary": "- Stock name, ticker, sector, exchange.\n- Current price & market cap.\n- Overall recommendation (Buy/Hold/Sell) with rationale.",
            "Key Highlights & Events": "- Latest earnings, guidance updates, M&A, partnerships, regulations.\n- Summarize news with sentiment and likely impact.",
            "Fundamental Analysis": "- Revenue, EBITDA, Net income, EPS growth.\n- Margins: gross, operating, net.\n- Cash flow, free cash flow, CapEx trend.\n- Balance sheet health (debt/equity, liquidity).\n- Returns: ROE, ROA, ROIC.\n- Valuation: P/E, EV/EBITDA, P/B, PEG.\n- Dividend yield & payout ratio.",
            "Technical Analysis": "- Recent price action, trend, support/resistance.\n- SMA, EMA, RSI, MACD, Bollinger Bands.\n- Volume, momentum, volatility.",
            "Price Movements & Event Impact": "- Compare recent events vs. stock price reaction.\n- Note volatility and volume spikes.",
            "Brokerage & Analyst Views": "- Summarize consensus rating (Buy/Hold/Sell %).\n- Track upgrades/downgrades, price target changes.",
            "Sector & Peer Comparison": "- Compare valuation & performance vs. 3–5 key peers.\n- Compare profitability, growth, leverage, and risk in a table.",
            "News & Developments": "- Summarize top news results (30–90 days).\n- Classify by category: earnings, regulation, macro, competition.\n- Provide sentiment analysis (positive/neutral/negative).",
            "Macroeconomic & Geopolitical Factors": "- Exposure to FX, commodity prices, tariffs, regulation.\n- Impact of rates, inflation, consumer demand trends.",
            "Risks & Red Flags": "- Operational, financial, regulatory, competitive risks.\n- Tail risks (low-probability, high-impact).",
            "Scenarios & Valuation Outlook": "- Base, Bull, Bear cases with assumptions.\n- Target price range and timeframe.\n- Key triggers to watch.",
            "Final Recommendation": "- Clear action: Buy / Hold / Sell.\n- Conviction level: High / Medium / Low.\n- Short-term vs. long-term view."
        }

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt)
        ])
        
        chain = prompt | llm_pro | StrOutputParser()
        
        try:
            section_content = await asyncio.wait_for(
                chain.ainvoke({
                    "context": context,
                    "section_name": section_name,
                    "framework": frameworks.get(section_name, "Provide a general analysis for this section."),
                    "char_count": len(context)
                }),
                timeout=300.0  # 5-minute timeout for each section generation
            )
            print(f"[{datetime.now()}] Successfully generated section: {section_name}")
            return f"## {section_name}\n\n{section_content}"
        except asyncio.TimeoutError:
            print(f"[{datetime.now()}] ERROR: Timeout generating section: {section_name}")
            return f"## {section_name}\n\nError: Timed out while generating this section."
        except Exception as e:
            print(f"[{datetime.now()}] ERROR: Exception generating section: {section_name} - {e}")
            return f"## {section_name}\n\nError: An exception occurred while generating this section."


    def _create_pdf_from_text(self, text: str) -> bytes:
        """Creates a PDF from a markdown-formatted string."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch,
            title=f"{self.company_name} Stock Research Analysis",
            author="AI Financial Analyst"
        )
        styles = getSampleStyleSheet()
        story = []

        # Title Page
        story.append(Paragraph(f"Comprehensive Equity Research: {self.company_name}", styles['h1']))
        story.append(Paragraph(f"Report Date: {self.today}", styles['h3']))
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph("Generated by AI Financial Analyst", styles['Italic']))
        story.append(PageBreak())

        for line in text.split('\n'):
            if line.startswith("## "):
                story.append(Spacer(1, 0.2 * inch))
                story.append(Paragraph(line.replace("## ", ""), styles['h2']))
            elif line.startswith("**"):
                story.append(Paragraph(line.replace("**", ""), styles['h3']))
            elif line.strip().startswith("- "):
                story.append(Paragraph(line, styles['Bullet']))
            elif line.strip():
                story.append(Paragraph(line, styles['BodyText']))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes