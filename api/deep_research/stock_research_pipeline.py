# /aigptssh/api/deep_research/stock_research_pipeline.py

import asyncio
import os
from datetime import datetime, timedelta
from io import BytesIO
import json
import time
import re

import aiohttp
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, PageBreak
from reportlab.lib import colors
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from api.serper_searcher import SerperNews
from api.dashboard.web_scraper import scrape_urls
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from api.news_rag.scoring_service import NewsRagScoringService

# --- Load Environment Variables ---
load_dotenv()

# --- Enhanced Debugging Start ---
print("[DEBUG] stock_research_pipeline.py: Module loading started.")

try:
    print("[DEBUG] Attempting to configure OpenAI API key...")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable not found.")
    print("INFO: OpenAI API key configured successfully.")

except Exception as e:
    print(f"CRITICAL ERROR: Failed to configure OpenAI API: {e}")
    raise

print("[DEBUG] Initializing gpt-4o-mini model...")
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, api_key=OPENAI_API_KEY)
print("[DEBUG] gpt-4o-mini model initialized.")
# --- Enhanced Debugging End ---


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
            delta = timedelta(days=amount * 30)  # Approximate
        else:
            delta = timedelta(days=0)
        
        return (datetime.now() - delta).strftime("%Y-%m-%d")
    
    # Try various date formats
    date_formats = [
        "%b %d, %Y",      # Dec 19, 2024
        "%d %b %Y",       # 24 Sept 2025
        "%B %d, %Y",      # December 19, 2024
        "%d %B %Y",       # 24 September 2025
        "%Y-%m-%d",       # 2024-12-19
        "%m/%d/%Y",       # 12/19/2024
        "%d/%m/%Y",       # 19/12/2024
    ]
    
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_string, fmt)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If all parsing fails, return current date
    print(f"WARNING: Could not parse date string: '{date_string}', using current date")
    return datetime.now().strftime("%Y-%m-%d")


class StockResearchPipeline:
    """
    A multi-step, sequential pipeline to generate a comprehensive stock research report.
    This version uses gpt-4o-mini for all language model tasks.
    """

    def __init__(self, company_name: str):
        print(f"[DEBUG] StockResearchPipeline.__init__ called for {company_name}")
        self.company_name = company_name
        self.brave_searcher = SerperNews(os.getenv("SERPER_API_KEY"))
        self.scoring_service = NewsRagScoringService()
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.report_sections = [
            "Executive Summary", "Key Highlights & Events", "Fundamental Analysis",
            "Technical Analysis", "Price Movements & Event Impact", "Brokerage & Analyst Views",
            "Sector & Peer Comparison", "News & Developments", "Macroeconomic & Geopolitical Factors",
            "Risks & Red Flags"
        ]
        print("[DEBUG] StockResearchPipeline instance created.")

    async def run(self):
        """
        Orchestrates the entire process of data gathering, analysis, and report generation sequentially.
        """
        start_time = time.time()
        print(f"[{datetime.now()}] --- Starting Advanced Stock Analysis for: {self.company_name} ---")

        # 1. Dynamically generate search queries
        print(f"\n[{datetime.now()}] [Step 1/5] Generating targeted search queries using gpt-4o-mini...")
        queries = await self._generate_search_queries()
        if not queries:
            print("[ERROR] Query generation failed or returned empty. Halting.")
            return None
        print(f"[{datetime.now()}] Generated {len(queries)} queries.")

        # 2. Gather all data sequentially
        print(f"\n[{datetime.now()}] [Step 2/5] Gathering data from {len(queries)} web sources sequentially...")
        scraped_articles = await self._gather_data(queries)
        print(f"[{datetime.now()}] Gathered and scraped {len(scraped_articles)} articles.")

        # 3. Get relevant context for each section
        print(f"\n[{datetime.now()}] [Step 3/5] Getting relevant context for each analysis section...")
        section_contexts = {}
        for section in self.report_sections:
            section_contexts[section] = await self._get_relevant_context(section, scraped_articles)

        # 4. Generate each report section sequentially
        print(f"\n[{datetime.now()}] [Step 4/5] Generating all 10 report sections sequentially using gpt-4o-mini...")
        report_parts = []
        for section in self.report_sections:
            section_content = await self._generate_section(section, section_contexts.get(section, ""))
            report_parts.append(section_content)

        final_report_text = "\n\n".join(report_parts)
        if not final_report_text.strip():
            print("Error: LLM failed to generate report sections.")
            return None
        print(f"[{datetime.now()}] All sections generated. Total report length: {len(final_report_text)} characters.")

        # 5. Create the PDF
        print(f"\n[{datetime.now()}] [Step 5/5] Assembling and creating the final PDF report...")
        try:
            pdf_buffer = await asyncio.get_event_loop().run_in_executor(
                None, self._create_pdf_from_text, final_report_text
            )
            print(f"[{datetime.now()}] PDF created successfully. Size: {len(pdf_buffer)} bytes")
        except Exception as e:
            print(f"[{datetime.now()}] ERROR creating PDF: {e}")
            return None

        end_time = time.time()
        print(f"\n[{datetime.now()}] --- Stock Research Pipeline Completed Successfully in {end_time - start_time:.2f} seconds ---")
        return pdf_buffer

    async def _generate_search_queries(self) -> list:
        """Uses gpt-4o-mini to create a list of specific search queries."""
        print("[DEBUG] _generate_search_queries: Awaiting LLM response...")
        parser = JsonOutputParser()
        prompt = ChatPromptTemplate.from_template(
            """
            For the company "{company_name}", generate a JSON list of 15 highly specific Serper search queries to gather data for a comprehensive financial research report. The queries should cover:
            1.  **Fundamentals**: P/E, EV/EBITDA, Debt/Equity, ROE, Revenue Growth, EPS.
            2.  **Technicals**: RSI, MACD, 50-day SMA, Support & Resistance levels.
            3.  **News & Events**: Latest earnings calls, M&A, partnerships, regulations.
            4.  **Analyst Views**: Consensus rating, price target upgrades/downgrades.
            5.  **Peer Comparison**: Top competitors, sector performance.
            6.  **Risks & Macro Factors**: Geopolitical risks, supply chain issues, regulatory changes.
            
            Return a JSON object with a single key "queries" containing the list of strings.
            {format_instructions}
            """,
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = prompt | llm | parser
        try:
            result = await chain.ainvoke({"company_name": self.company_name})
            print("[DEBUG] _generate_search_queries: LLM response received.")
            return result.get("queries", [])
        except Exception as e:
            print(f"[ERROR] _generate_search_queries: LLM call failed: {e}")
            return []

    async def _gather_data(self, queries: list) -> list:
        """Executes search queries sequentially with a delay, scrapes URLs, and returns all content."""
        all_articles = []
        async with aiohttp.ClientSession(**self.brave_searcher.session_config) as session:
            for query in queries:
                success = False
                for attempt in range(3):
                    try:
                        result = await self.brave_searcher.search_and_scrape(session, query, max_sources=10)
                        # Normalize dates in the articles
                        for article in result:
                            if 'publication_date' in article:
                                article['publication_date'] = parse_flexible_date(article['publication_date'])
                        all_articles.extend(result)
                        print(f"Successfully scraped for query: {query}")
                        await asyncio.sleep(1.1)
                        success = True
                        break
                    except Exception as e:
                        print(f"Brave search failed for query '{query}' (attempt {attempt + 1}): {e}. Retrying...")
                        await asyncio.sleep(2 ** attempt)
                if not success:
                    print(f"All retries failed for query '{query}'.")

        unique_urls = {article["link"]: article for article in all_articles if article.get("link")}.values()
        
        if not unique_urls:
            return []
            
        scraped_articles = await scrape_urls(list(unique_urls))
        return scraped_articles
    
    async def _get_relevant_context(self, section_name: str, scraped_articles: list) -> str:
        """Reranks content chunks and creates an enhanced context for a specific section."""
        query = f"Information for {section_name} of {self.company_name} stock report"
        reranked_chunks = await self.scoring_service.rerank_content_chunks(query, scraped_articles, top_n=5)
        return self.scoring_service.create_enhanced_context(reranked_chunks)

    async def _generate_section(self, section_name: str, context: str) -> str:
        """Generates the content for a single report section using gpt-4o-mini with a long timeout."""
        if not context:
            return f"## {section_name}\n\nData not available in the provided sources for this section."
        today = datetime.now().strftime("%Y-%m-%d")
        system_prompt = f"""
        You are a financial analyst AI writing the "{section_name}" section of a research report for {self.company_name} on {self.today}.
        Today's date is {today}, make sure your answers use today as reference.    
        Your analysis must be based ONLY on the provided context.
        If the context is insufficient, state that data was not available.
        Use markdown for formatting. Be structured, evidence-based, and investment-grade.
        **CRITICAL INSTRUCTION: Do NOT use markdown tables. Present any tabular data using bullet points or a simple text layout.**
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
            "Sector & Peer Comparison": "- Compare valuation & performance vs. 3–5 key peers.\n- Compare profitability, growth, leverage, and risk.",
            "News & Developments": "- Summarize top news results (30–90 days).\n- Classify by category: earnings, regulation, macro, competition.\n- Provide sentiment analysis (positive/neutral/negative).",
            "Macroeconomic & Geopolitical Factors": "- Exposure to FX, commodity prices, tariffs, regulation.\n- Impact of rates, inflation, consumer demand trends.",
            "Risks & Red Flags": "- Operational, financial, regulatory, competitive risks.\n- Tail risks (low-probability, high-impact).",
        }

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt)
        ])
        
        chain = prompt | llm | StrOutputParser()
        
        try:
            section_content = await asyncio.wait_for(
                chain.ainvoke({
                    "context": context,
                    "section_name": section_name,
                    "framework": frameworks.get(section_name, "Provide a general analysis for this section."),
                    "char_count": len(context)
                }),
                timeout=300.0
            )
            print(f"[{datetime.now()}] Successfully generated section: {section_name}")
            return f"## {section_name}\n\n{section_content}"
        except asyncio.TimeoutError:
            print(f"[{datetime.now()}] ERROR: Timeout generating section: {section_name}")
            return f"## {section_name}\n\nError: Timed out while generating this section."
        except Exception as e:
            print(f"[{datetime.now()}] ERROR: Exception generating section: {section_name} - {e}")
            return f"## {section_name}\n\nError: An exception occurred while generating this section."

    def _sanitize_text_for_pdf(self, text: str) -> str:
        """
        Sanitize text to avoid reportlab issues with special characters.
        """
        # Replace problematic characters
        text = text.replace('\u2019', "'")  # Right single quotation mark
        text = text.replace('\u2018', "'")  # Left single quotation mark
        text = text.replace('\u201c', '"')  # Left double quotation mark
        text = text.replace('\u201d', '"')  # Right double quotation mark
        text = text.replace('\u2013', '-')  # En dash
        text = text.replace('\u2014', '-')  # Em dash
        text = text.replace('\u2026', '...')  # Ellipsis
        
        # Remove or replace other non-ASCII characters that might cause issues
        text = ''.join(char if ord(char) < 128 or char.isspace() else '?' for char in text)
        
        return text

    def _create_pdf_from_text(self, text: str) -> bytes:
        """Creates a PDF from a markdown-formatted string."""
        print(f"[DEBUG] Starting PDF creation. Text length: {len(text)} characters")
        
        # Sanitize the text first
        text = self._sanitize_text_for_pdf(text)
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch,
            title=f"{self.company_name} Stock Research Analysis",
            author="AI Financial Analyst"
        )
        styles = getSampleStyleSheet()
        
        # Only add styles if they don't already exist
        if 'h1' not in styles:
            styles.add(ParagraphStyle(name='h1', fontSize=24, leading=28, spaceAfter=20, alignment=1))
        if 'h2' not in styles:
            styles.add(ParagraphStyle(name='h2', fontSize=18, leading=22, spaceBefore=10, spaceAfter=10))
        if 'h3' not in styles:
            styles.add(ParagraphStyle(name='h3', fontSize=14, leading=18, spaceBefore=8, spaceAfter=8))
        if 'Bullet' not in styles:
            styles.add(ParagraphStyle(name='Bullet', parent=styles['BodyText'], firstLineIndent=0, spaceBefore=3, leftIndent=18))

        styles['Normal'].wordWrap = 'CJK'
        if 'Bullet' in styles:
            styles['Bullet'].wordWrap = 'CJK'
        
        story = []

        # Title Page
        story.append(Paragraph(f"Comprehensive Equity Research: {self.company_name}", styles['h1']))
        story.append(Paragraph(f"Report Date: {self.today}", styles['h3']))
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph("Generated by AI Financial Analyst", styles['Italic']))
        story.append(PageBreak())

        print(f"[DEBUG] Processing {len(text.split(chr(10)))} lines for PDF")
        
        for i, line in enumerate(text.split('\n')):
            try:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith("## "):
                    story.append(PageBreak())
                    story.append(Spacer(1, 0.2 * inch))
                    clean_line = line.replace("## ", "")
                    story.append(Paragraph(clean_line, styles['h2']))
                elif line.startswith("**"):
                    clean_line = line.replace("**", "")
                    story.append(Paragraph(clean_line, styles['h3']))
                elif line.strip().startswith("- "):
                    story.append(Paragraph(line, styles['Bullet']))
                else:
                    # Split very long lines to avoid reportlab issues
                    if len(line) > 500:
                        chunks = [line[i:i+500] for i in range(0, len(line), 500)]
                        for chunk in chunks:
                            story.append(Paragraph(chunk, styles['Normal']))
                    else:
                        story.append(Paragraph(line, styles['Normal']))
            except Exception as e:
                print(f"[WARNING] Error processing line {i}: {e}")
                print(f"[WARNING] Problematic line: {line[:100]}...")
                continue

        print(f"[DEBUG] Building PDF with {len(story)} elements")
        
        try:
            doc.build(story)
            pdf_bytes = buffer.getvalue()
            print(f"[DEBUG] PDF built successfully. Size: {len(pdf_bytes)} bytes")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to build PDF: {e}")
            import traceback
            traceback.print_exc()
            # Return a simple error PDF instead of crashing
            error_text = f"Error generating PDF: {e}\n\nPlease check the logs for details."
            return error_text.encode('utf-8')
        finally:
            buffer.close()

        return pdf_bytes