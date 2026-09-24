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
from reportlab.lib.pagesizes import letter
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, PageBreak, 
    Table, TableStyle, KeepTogether
)
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
            delta = timedelta(days=amount * 30)
        else:
            delta = timedelta(days=0)
        
        return (datetime.now() - delta).strftime("%Y-%m-%d")
    
    # Try various date formats
    date_formats = [
        "%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y",
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y",
    ]
    
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_string, fmt)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    print(f"WARNING: Could not parse date string: '{date_string}', using current date")
    return datetime.now().strftime("%Y-%m-%d")


class StockResearchPipeline:
    """
    A multi-step, sequential pipeline to generate a comprehensive stock research report.
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
            For the company "{company_name}", generate a JSON list of 15 highly specific search queries to gather comprehensive financial data. Focus on queries that will return actual numbers and metrics:
            
            1. **Fundamentals** (5 queries): 
                - "{company_name}" quarterly results revenue profit margin
                - "{company_name}" balance sheet debt equity ratio financial statements
                - "{company_name}" PE ratio valuation metrics
                - "{company_name}" cash flow free cash flow
                - "{company_name}" ROE ROIC return metrics
            
            2. **Technicals** (2 queries): 
                - "{company_name}" stock technical analysis RSI MACD
                - "{company_name}" share price support resistance levels
            
            3. **News & Events** (3 queries): 
                - "{company_name}" latest earnings call results
                - "{company_name}" recent news acquisitions partnerships
                - "{company_name}" management guidance outlook
            
            4. **Analyst Views** (2 queries): 
                - "{company_name}" analyst rating price target
                - "{company_name}" brokerage recommendation upgrade downgrade
            
            5. **Peer Comparison** (2 queries): 
                - "{company_name}" vs competitors comparison
                - "{company_name}" sector performance peer analysis
            
            6. **Risks** (1 query): 
                - "{company_name}" risks challenges regulatory issues
            
            Generate queries that are likely to return specific financial data, news articles, and analyst reports.
            Return a JSON object with a single key "queries" containing the list of 15 strings.
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
                        result = await self.brave_searcher.search_and_scrape(session, query, max_sources=20)
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
        reranked_chunks = await self.scoring_service.rerank_content_chunks(query, scraped_articles, top_n=10)
        return self.scoring_service.create_enhanced_context(reranked_chunks)

    async def _generate_section(self, section_name: str, context: str) -> str:
        """Generates the content for a single report section using gpt-4o-mini with a long timeout."""
        if not context:
            return f"## {section_name}\n\nInsufficient data available in the provided sources for detailed analysis of this section."
        
        today = datetime.now().strftime("%Y-%m-%d")
        system_prompt = f"""
        You are an expert financial analyst writing the "{section_name}" section of an investment research report for {self.company_name} on {self.today}.
        
        CRITICAL FORMATTING RULES:
        - Use clear markdown formatting with proper hierarchy
        - Use **bold** for key metrics, numbers, and important conclusions
        - Use bullet points (with -) for lists - NEVER use numbered lists
        - Keep paragraphs concise (3-4 sentences max)
        - Use subheadings (###) to organize content within the section
        - DO NOT use markdown tables - use bullet points with clear labels instead
        - Start with a brief 2-3 sentence overview of the section
        - End with a 2-3 sentence key takeaway or conclusion
        - Write in present tense when discussing current data
        - Use past tense only for historical events
        
        CONTENT QUALITY RULES:
        - Always cite specific numbers with units (Rs, %, Million, etc.)
        - Include dates for all time-referenced data
        - Compare current metrics to historical performance when possible
        - Highlight trends (improving/declining/stable)
        - If a metric is missing, briefly mention it's unavailable and move on
        - Focus on the most material and actionable information
        - Avoid generic statements - be specific
        
        Your analysis must be:
        - Evidence-based and factual
        - Well-structured and easy to scan
        - Investment-grade quality
        - Based ONLY on the provided context
        - Professional but accessible
        """
        
        human_prompt = """
        **Context for your analysis:**
        {context}

        **Analysis Framework for "{section_name}":**
        {framework}
        
        Write a comprehensive, well-formatted "{section_name}" section following the framework above.
        Focus on actionable insights and key takeaways for investors.
        """
        
        frameworks = {
            "Executive Summary": """
            ### Structure:
            - **Company Overview**: Name, ticker, sector, exchange, current price, market cap
            - **Investment Thesis**: 2-3 sentence summary of the opportunity/risk
            - **Key Metrics**: Highlight 3-5 critical financial metrics
            - **Recommendation**: Clear Buy/Hold/Sell with concise rationale (2-3 bullet points)
            - **Risk Assessment**: Brief mention of top 2-3 risks
            """,
            
            "Key Highlights & Events": """
            ### Recent Major Events (Last 90 Days):
            - **Earnings Results**: Latest quarter performance vs expectations
            - **Corporate Actions**: M&A, partnerships, management changes
            - **Market Moving News**: Significant announcements with dates
            - **Stock Reactions**: Price movement correlation with events
            
            For each event: Date, Description, Market Impact (positive/negative/neutral)
            """,
            
            "Fundamental Analysis": """
            ### Financial Performance:
            - **Revenue & Growth**: Recent trends with YoY/QoQ comparisons
            - **Profitability**: Margins (gross, operating, net) and trends
            - **Cash Generation**: Free cash flow, operating cash flow
            
            ### Balance Sheet:
            - **Leverage**: Debt/Equity ratio and debt sustainability
            - **Liquidity**: Current ratio, cash position
            
            ### Returns:
            - **ROE, ROA, ROIC**: Current levels and peer comparison
            
            ### Valuation:
            - **Multiples**: P/E, EV/EBITDA, P/B, PEG ratios
            - **Dividend**: Yield and payout ratio if applicable
            
            Format each metric as: **Metric Name**: Value (comparison/context)
            """,
            
            "Technical Analysis": """
            ### Current Technical Picture:
            - **Price Action**: Current price, recent trend (bullish/bearish)
            - **Key Levels**: 
              - Support levels with prices
              - Resistance levels with prices
            
            ### Technical Indicators:
            - **Moving Averages**: 50-day SMA, 200-day SMA positions
            - **Momentum**: RSI level and interpretation
            - **MACD**: Signal and trend indication
            
            ### Trading Characteristics:
            - **Volume**: Recent volume trends
            - **Volatility**: Current volatility assessment
            
            Provide clear buy/sell signals if applicable.
            """,
            
            "Price Movements & Event Impact": """
            ### Price Performance Analysis:
            - **Recent Movements**: Key price changes in last 30-90 days with dates
            - **Event Correlation**: How stock reacted to specific events
            - **Volatility Spikes**: Unusual trading days with explanation
            - **Volume Analysis**: Volume patterns around key events
            
            Format: [Date] - [Event] → [Price Impact %] ([Volume trend])
            """,
            
            "Brokerage & Analyst Views": """
            ### Analyst Consensus:
            - **Rating Distribution**: Buy/Hold/Sell percentages
            - **Price Targets**: Average, high, low targets
            
            ### Recent Changes:
            - **Upgrades**: List with firm name, date, reason
            - **Downgrades**: List with firm name, date, reason
            - **Price Target Changes**: Significant revisions
            
            ### Key Analyst Themes:
            - Common bullish arguments
            - Common bearish concerns
            """,
            
            "Sector & Peer Comparison": """
            ### Competitive Positioning:
            - List 3-5 key direct competitors
            
            ### Comparative Analysis:
            - **Valuation**: Compare P/E, EV/EBITDA vs peers
            - **Growth**: Revenue and earnings growth vs sector
            - **Profitability**: Margin comparison
            - **Financial Health**: Debt levels vs peers
            
            ### Sector Trends:
            - Current sector performance
            - {self.company_name}'s relative strength/weakness
            
            Format comparisons clearly with company vs peer metrics.
            """,
            
            "News & Developments": """
            ### Recent News Summary (30-90 Days):
            
            Categorize and summarize news by:
            
            #### Earnings & Financial:
            - Key financial announcements
            
            #### Strategic & Operational:
            - Business developments, partnerships
            
            #### Regulatory & Legal:
            - Regulatory changes, compliance issues
            
            #### Market & Competition:
            - Competitive dynamics, market share
            
            For each item: [Date] - **Headline/Summary** (Sentiment: Positive/Neutral/Negative)
            """,
            
            "Macroeconomic & Geopolitical Factors": """
            ### Macro Exposures:
            - **Interest Rates**: Impact of rate changes on business
            - **Inflation**: Cost pressure effects
            - **Currency**: FX exposure and impact
            - **Commodities**: Key commodity price sensitivity
            
            ### Sector-Specific Factors:
            - Industry-specific economic drivers
            - Consumer demand trends
            - Supply chain considerations
            
            ### Geopolitical Risks:
            - Regulatory environment
            - Trade policies and tariffs
            - Regional political risks
            
            Assess each factor's potential impact: High/Medium/Low
            """,
            
            "Risks & Red Flags": """
            ### Risk Categories:
            
            #### Operational Risks:
            - Business execution challenges
            - Supply chain vulnerabilities
            
            #### Financial Risks:
            - Balance sheet concerns
            - Liquidity issues
            - Earnings volatility
            
            #### Regulatory/Legal Risks:
            - Compliance challenges
            - Pending litigation
            
            #### Competitive Risks:
            - Market share threats
            - Disruptive competition
            
            #### Tail Risks:
            - Low probability, high impact scenarios
            
            For each risk: Description, Probability (High/Med/Low), Potential Impact
            """
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
        """Sanitize text to avoid reportlab issues with special characters."""
        # Replace Indian Rupee symbol
        text = text.replace('₹', 'Rs ')
        
        # Replace problematic characters
        replacements = {
            '\u2019': "'", '\u2018': "'",
            '\u201c': '"', '\u201d': '"',
            '\u2013': '-', '\u2014': '-',
            '\u2026': '...', '\u2022': '*',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Keep only ASCII and common whitespace
        text = ''.join(char if ord(char) < 128 or char.isspace() else '' for char in text)
        
        return text

    def _create_pdf_from_text(self, text: str) -> bytes:
        """Creates a beautiful, professional PDF from markdown-formatted text."""
        print(f"[DEBUG] Starting PDF creation. Text length: {len(text)} characters")
        
        # Sanitize text
        text = self._sanitize_text_for_pdf(text)
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch, 
            leftMargin=0.75*inch, 
            topMargin=0.75*inch, 
            bottomMargin=0.75*inch,
            title=f"{self.company_name} Stock Research Analysis",
            author="AI Financial Analyst"
        )
        
        # Define beautiful styles
        styles = getSampleStyleSheet()
        
        # Custom styles for professional look
        if 'CustomTitle' not in styles:
            styles.add(ParagraphStyle(
                name='CustomTitle',
                parent=styles['Heading1'],
                fontSize=28,
                leading=34,
                textColor=colors.HexColor('#1a1a2e'),
                spaceAfter=12,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            ))
        
        if 'CustomSubtitle' not in styles:
            styles.add(ParagraphStyle(
                name='CustomSubtitle',
                parent=styles['Normal'],
                fontSize=12,
                leading=16,
                textColor=colors.HexColor('#666666'),
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName='Helvetica'
            ))
        
        if 'SectionHeader' not in styles:
            styles.add(ParagraphStyle(
                name='SectionHeader',
                parent=styles['Heading1'],
                fontSize=20,
                leading=24,
                textColor=colors.HexColor('#16213e'),
                spaceBefore=24,
                spaceAfter=12,
                fontName='Helvetica-Bold',
                borderWidth=0,
                borderColor=colors.HexColor('#0f3460'),
                borderPadding=5,
                leftIndent=0
            ))
        
        if 'SubSectionHeader' not in styles:
            styles.add(ParagraphStyle(
                name='SubSectionHeader',
                parent=styles['Heading2'],
                fontSize=14,
                leading=18,
                textColor=colors.HexColor('#0f3460'),
                spaceBefore=12,
                spaceAfter=8,
                fontName='Helvetica-Bold'
            ))
        
        if 'CustomBody' not in styles:
            styles.add(ParagraphStyle(
                name='CustomBody',
                parent=styles['Normal'],
                fontSize=11,
                leading=16,
                textColor=colors.HexColor('#2c2c2c'),
                spaceAfter=8,
                alignment=TA_JUSTIFY,
                fontName='Helvetica'
            ))
        
        if 'CustomBullet' not in styles:
            styles.add(ParagraphStyle(
                name='CustomBullet',
                parent=styles['Normal'],
                fontSize=11,
                leading=15,
                textColor=colors.HexColor('#2c2c2c'),
                leftIndent=20,
                firstLineIndent=0,
                spaceBefore=4,
                spaceAfter=4,
                bulletIndent=10,
                fontName='Helvetica'
            ))
        
        if 'HighlightBox' not in styles:
            styles.add(ParagraphStyle(
                name='HighlightBox',
                parent=styles['Normal'],
                fontSize=11,
                leading=15,
                textColor=colors.HexColor('#1a1a2e'),
                spaceAfter=10,
                spaceBefore=10,
                leftIndent=15,
                rightIndent=15,
                fontName='Helvetica-Bold'
            ))
        
        story = []
        
        # Beautiful title page with colored box
        story.append(Spacer(1, 1.5*inch))
        
        # Title in a colored box
        title_table = Table(
            [[Paragraph(f"<b>{self.company_name}</b>", styles['CustomTitle'])]],
            colWidths=[6.5*inch]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#16213e')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 20),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(title_table)
        
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph(
            "Comprehensive Equity Research Report",
            styles['CustomSubtitle']
        ))
        story.append(Spacer(1, 0.5*inch))
        
        # Info table for report metadata
        info_data = [
            [Paragraph("<b>Report Date:</b>", styles['CustomBody']), 
             Paragraph(self.today, styles['CustomBody'])],
            [Paragraph("<b>Analyst:</b>", styles['CustomBody']), 
             Paragraph("AI Financial Analyst", styles['CustomBody'])],
            [Paragraph("<b>Report Type:</b>", styles['CustomBody']), 
             Paragraph("Fundamental & Technical Analysis", styles['CustomBody'])],
        ]
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(info_table)
        
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(
            "<i>This report is generated using advanced AI analysis of publicly available information. "
            "It should be used for informational purposes only and not as the sole basis for investment decisions.</i>",
            styles['CustomSubtitle']
        ))
        story.append(PageBreak())
        
        # Table of Contents
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("<b>Table of Contents</b>", styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))
        
        toc_data = []
        for idx, section in enumerate(self.report_sections, 1):
            toc_data.append([
                Paragraph(f"{idx}.", styles['CustomBody']),
                Paragraph(section, styles['CustomBody']),
                Paragraph(f"Page {idx + 2}", styles['CustomBody'])
            ])
        
        toc_table = Table(toc_data, colWidths=[0.5*inch, 5*inch, 1*inch])
        toc_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.HexColor('#e0e0e0')),
        ]))
        story.append(toc_table)
        story.append(PageBreak())
        
        # Process content
        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            try:
                # Section headers (##)
                if line.startswith("## "):
                    story.append(PageBreak())
                    story.append(Spacer(1, 0.3*inch))
                    clean_line = line.replace("## ", "").strip()
                    
                    # Create a header with colored background
                    header_table = Table(
                        [[Paragraph(f"<b>{clean_line}</b>", styles['SectionHeader'])]],
                        colWidths=[6.5*inch]
                    )
                    header_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e8f4f8')),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TOPPADDING', (0, 0), (-1, -1), 12),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                        ('LEFTPADDING', (0, 0), (-1, -1), 15),
                        ('LINEABOVE', (0, 0), (-1, 0), 3, colors.HexColor('#0f3460')),
                    ]))
                    story.append(header_table)
                    story.append(Spacer(1, 0.15*inch))
                
                # Subsection headers (###)
                elif line.startswith("### "):
                    clean_line = line.replace("### ", "").strip()
                    story.append(Spacer(1, 0.1*inch))
                    story.append(Paragraph(clean_line, styles['SubSectionHeader']))
                
                # Bullet points
                elif line.startswith("- ") or line.startswith("* "):
                    clean_line = line[2:].strip()
                    
                    # Handle bold within bullets
                    if "**" in clean_line:
                        clean_line = clean_line.replace("**", "<b>", 1).replace("**", "</b>", 1)
                        # Handle any remaining ** pairs
                        while "**" in clean_line:
                            clean_line = clean_line.replace("**", "<b>", 1).replace("**", "</b>", 1)
                    
                    bullet_text = f"• {clean_line}"
                    story.append(Paragraph(bullet_text, styles['CustomBullet']))
                
                # Bold text paragraphs (can be key insights)
                elif line.startswith("**") and line.endswith("**"):
                    clean_line = line.replace("**", "").strip()
                    
                    # Check if this is a "Key Takeaway" or "Key Insight"
                    if any(keyword in clean_line.lower() for keyword in ['key takeaway', 'key insight', 'important:', 'note:']):
                        # Create a highlighted box
                        highlight_table = Table(
                            [[Paragraph(f"<b>{clean_line}</b>", styles['HighlightBox'])]],
                            colWidths=[6*inch]
                        )
                        highlight_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fff9e6')),
                            ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#ffd700')),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('TOPPADDING', (0, 0), (-1, -1), 10),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                            ('LEFTPADDING', (0, 0), (-1, -1), 15),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
                        ]))
                        story.append(highlight_table)
                    else:
                        story.append(Paragraph(f"<b>{clean_line}</b>", styles['BoldText']))
                
                # Regular paragraphs
                else:
                    # Handle inline bold
                    if "**" in line:
                        line = line.replace("**", "<b>", 1).replace("**", "</b>", 1)
                        while "**" in line:
                            line = line.replace("**", "<b>", 1).replace("**", "</b>", 1)
                    
                    # Split very long paragraphs
                    if len(line) > 600:
                        chunks = [line[j:j+600] for j in range(0, len(line), 600)]
                        for chunk in chunks:
                            story.append(Paragraph(chunk, styles['CustomBody']))
                    else:
                        story.append(Paragraph(line, styles['CustomBody']))
                
            except Exception as e:
                print(f"[WARNING] Error processing line {i}: {e}")
                print(f"[WARNING] Problematic line: {line[:100]}...")
            
            i += 1
        
        print(f"[DEBUG] Building PDF with {len(story)} elements")
        
        try:
            doc.build(story)
            pdf_bytes = buffer.getvalue()
            print(f"[DEBUG] PDF built successfully. Size: {len(pdf_bytes)} bytes")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to build PDF: {e}")
            import traceback
            traceback.print_exc()
            error_text = f"Error generating PDF: {e}\n\nPlease check the logs for details."
            return error_text.encode('utf-8')
        finally:
            buffer.close()
        
        return pdf_bytes