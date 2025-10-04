# /aigptssh/api/deep_research/stock_research_pipeline.py
import asyncio
import os
from datetime import datetime
from io import BytesIO

import aiohttp
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from api.brave_searcher import BraveNews
from api.dashboard.web_scraper import scrape_urls
from config import GPT4o_mini as llm
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate


class StockResearchPipeline:
    """
    A pipeline to generate a comprehensive stock research report for a given company,
    using only Brave Search for data gathering and a detailed analysis framework.
    """

    def __init__(self, company_name: str):
        self.company_name = company_name
        self.brave_searcher = BraveNews(os.getenv("BRAVE_API_KEY"))

    async def run(self):
        """
        Orchestrates the entire process of data gathering, analysis, and report generation.
        """
        print(f"--- Starting Comprehensive Stock Analysis for: {self.company_name} ---")

        # Create a single session to be used for all API calls
        async with aiohttp.ClientSession(
            **self.brave_searcher.session_config
        ) as session:
            # Step 1 & 2: Gather All Data via Brave Search
            print(
                "\n[Step 1 & 2/4] Gathering quantitative and qualitative data via Brave Search..."
            )
            all_data_context = await self._get_all_data(session)

        # Step 3: Synthesize and Generate Report
        print("\n[Step 3/4] Synthesizing data and generating the report...")
        report_text = await self._generate_report_text(all_data_context)
        if not report_text or not report_text.strip():
            print("Error: LLM returned an empty report. Halting pipeline.")
            return None

        # Step 4: Create PDF
        print("\n[Step 4/4] Creating PDF document...")
        pdf_buffer = self._create_pdf_from_text(report_text)
        print("\n--- Stock Research Pipeline Completed Successfully ---")
        return pdf_buffer

    async def _get_all_data(self, session: aiohttp.ClientSession):
        """
        Gathers all necessary data (quantitative and qualitative) using a comprehensive
        set of targeted search queries.
        """
        queries = [
            # For Executive Summary & Fundamentals
            f"{self.company_name} stock overview and current price",
            f"{self.company_name} latest financial statements",
            f"{self.company_name} key financial ratios",
            f"{self.company_name} valuation multiples (P/E, EV/EBITDA, P/B)",
            f"{self.company_name} dividend history and payout ratio",
            # For Technical Analysis
            f"{self.company_name} stock technical analysis and charts",
            f"technical indicators for {self.company_name} (RSI, MACD, SMA)",
            # For News, Events, and Analyst Views
            f"{self.company_name} latest news and events",
            f"{self.company_name} analyst ratings and price targets",
            f"{self.company_name} brokerage reports summary",
            # For Sector & Peer Comparison
            f"{self.company_name} top competitors and peer analysis",
            f"sector performance analysis for {self.company_name}",
            # For Macro Factors & Risks
            f"{self.company_name} macroeconomic and geopolitical risks",
            f"{self.company_name} company risks and red flags",
        ]

        tasks = [
            self.brave_searcher.search_and_scrape(session, query, max_sources=3)
            for query in queries
        ]
        results = await asyncio.gather(*tasks)
        all_articles = [article for result in results for article in result]

        unique_urls = {article["link"]: article for article in all_articles}.values()
        scraped_articles = await scrape_urls(list(unique_urls))

        # Combine all scraped content into a single context string
        return "\n\n---\n\n".join(
            [
                f"Source URL: {article.get('url', '')}\nSource Title: {article.get('title', '')}\n\n{article.get('content', '')}"
                for article in scraped_articles
                if article.get("content")
            ]
        )

    async def _generate_report_text(self, context: str) -> str:
        """
        Uses a powerful LLM to generate a structured research report from the scraped text data,
        following the detailed analysis framework.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        template = """
        You are a highly skilled financial research analyst AI. Your task is to conduct detailed equity research on a given stock, integrating fundamental analysis, technical analysis, news & events, sector & peer performance, broker/analyst views, and macro/geopolitical impacts. You must produce an output that is structured, evidence-based, and investment-grade. Use the provided Brave Search API results for all data points.

        **Stock:** {company_name}
        **Today's Date:** {today}

        **Collected Data from Web Search:**
        {context}

        ---
        **ANALYSIS FRAMEWORK**
        ---

        Please generate a detailed report with the following sections. Extract all necessary information from the **Collected Data** provided above. If data for a specific point is not available in the context, explicitly state that it was not found in the provided sources. Use markdown for formatting.

        **1. Executive Summary**
           - Stock name, ticker, sector, exchange.
           - Current price & market cap.
           - Overall recommendation (Buy/Hold/Sell) with a concise rationale based on your analysis.

        **2. Key Highlights & Events**
           - Latest earnings, guidance updates, M&A, partnerships, regulations from the news.
           - Summarize recent news with sentiment and likely impact.

        **3. Fundamental Analysis**
           - Revenue, EBITDA, Net income, EPS growth (YoY, 3Y CAGR if available).
           - Margins: gross, operating, net.
           - Cash flow, free cash flow, CapEx trend.
           - Balance sheet health (debt/equity, liquidity, net debt/EBITDA).
           - Returns: ROE, ROA, ROIC.
           - Valuation: P/E, EV/EBITDA, P/B, PEG ratio.
           - Dividend yield & payout ratio.

        **4. Technical Analysis**
           - Recent price action, trend, support/resistance levels.
           - Key technical indicator values (SMA, EMA, RSI, MACD) and their interpretation.
           - Volume, momentum, and volatility.

        **5. Price Movements & Event Impact**
           - Correlate recent events from the news with stock price reactions.
           - Note any volatility and volume spikes around key announcements.

        **6. Brokerage & Analyst Views**
           - Summarize consensus rating (e.g., Buy/Hold/Sell percentages).
           - Note any recent upgrades/downgrades or changes in price targets.
           - Highlight any diverging opinions among analysts.

        **7. Sector & Peer Comparison**
           - Create a comparison table for valuation & performance vs. 3–5 key peers mentioned in the context.
           - Compare profitability, growth, and leverage.

        **8. News & Developments (30–90 days)**
           - Summarize the top news results from the context.
           - Classify news by category: earnings, regulation, macro, competition.
           - Provide a sentiment analysis (positive/neutral/negative) for the news.

        **9. Macroeconomic & Geopolitical Factors**
           - Identify exposure to FX, commodity prices, tariffs, and regulation.
           - Discuss the impact of interest rates, inflation, and consumer trends.

        **10. Risks & Red Flags**
            - List operational, financial, regulatory, and competitive risks.
            - Mention any low-probability, high-impact tail risks identified.

        **11. Scenarios & Valuation Outlook**
            - Formulate Base, Bull, and Bear cases with key assumptions based on the analysis.
            - Provide a target price range and timeframe.
            - List key triggers to watch for each scenario.

        **12. Final Recommendation**
            - State a clear action: Buy / Hold / Sell.
            - Specify your conviction level: High / Medium / Low.
            - Provide both a short-term and long-term view.
        """
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | llm | StrOutputParser()

        response = await chain.ainvoke(
            {
                "company_name": self.company_name,
                "today": today,
                "context": context,
            }
        )
        return response

    def _create_pdf_from_text(self, text: str) -> bytes:
        """Creates a PDF from a markdown-formatted string."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
            title=f"{self.company_name} Stock Research Analysis",
            author="AI Financial Analyst",
        )
        styles = getSampleStyleSheet()
        story = []

        for line in text.split("\n"):
            if line.startswith("## "):
                story.append(Paragraph(line.replace("## ", ""), styles["h2"]))
                story.append(Spacer(1, 0.2 * inch))
            elif line.startswith("**"):
                story.append(Paragraph(line.replace("**", ""), styles["h3"]))
            elif line.strip():
                story.append(Paragraph(line, styles["BodyText"]))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes