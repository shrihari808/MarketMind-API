"""
Deep Equity Research Pipeline Service.
Orchestrates institutional-grade equity research reports incorporating fundamentals,
multi-angle web retrieval, risks, catalysts, valuation, and ReportLab PDF export.
"""

import asyncio
from datetime import datetime, timezone
from io import BytesIO
import re
from typing import Optional, List, Dict
from app.core.logging import logger
from app.domain.interfaces.llm import LLMClient
from app.domain.interfaces.market import MarketDataClient
from app.domain.interfaces.scraper import WebScraper
from app.domain.interfaces.search import SearchEngine
from app.domain.schemas.market import StockFundamentals, StockQuote
from app.domain.schemas.rag import DeepResearchResult, SourceCitation
from app.infrastructure.llm.gemini import GeminiLLMClient
from app.infrastructure.market.yfinance_client import YFinanceMarketClient
from app.infrastructure.scrapers.web_scraper import TrafilaturaWebScraper
from app.infrastructure.search.factory import SearchEngineFactory


class DeepResearchService:
    """Automated institutional equity research report orchestrator."""

    SYSTEM_PROMPT = (
        "You are a CFA Charterholder and Lead Equity Research Analyst at a premier investment bank. "
        "Your task is to write an institutional-grade, exhaustive Equity Research Report. "
        "Your report must be thoroughly grounded in empirical financial metrics, verified news, "
        "and clear strategic reasoning.\n\n"
        "Formatting Guidelines:\n"
        "- Use clear, professional Markdown headings (## and ###).\n"
        "- Format balance sheet and valuation metrics in structured Markdown tables.\n"
        "- Every critical section must have concrete takeaways.\n"
        "- Emphasize risk asymmetry and catalyst timing."
    )

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        market_client: Optional[MarketDataClient] = None,
        search_engine: Optional[SearchEngine] = None,
        scraper: Optional[WebScraper] = None
    ):
        self.llm = llm_client or GeminiLLMClient()
        self.market = market_client or YFinanceMarketClient()
        self.search_engine = search_engine or SearchEngineFactory.get_search_engine()
        self.scraper = scraper or TrafilaturaWebScraper(timeout_seconds=8)

    async def generate_research_report(
        self,
        company_or_ticker: str,
        country: str = "IN",
        section_by_section: Optional[bool] = None
    ) -> DeepResearchResult:
        """
        Runs the end-to-end equity research pipeline for a company.
        Supports both single-pass synthesis and modular section-by-section multi-prompt generation.
        """
        from app.core.config import get_settings
        settings = get_settings()
        use_sectional = section_by_section if section_by_section is not None else settings.RESEARCH_SECTION_BY_SECTION

        logger.info(
            f"[DeepResearchService] Starting deep equity research on: '{company_or_ticker}' "
            f"(country={country}, section_by_section={use_sectional})"
        )
        created_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Step 1: Resolve Ticker
        ticker = await self.market.resolve_ticker(company_or_ticker) or company_or_ticker
        logger.info(f"[DeepResearchService] Resolved ticker symbol: '{company_or_ticker}' -> '{ticker}'")

        # Step 2: Fetch Fundamentals & Market Quote in Parallel
        logger.info(f"[DeepResearchService] Concurrently fetching fundamentals and real-time quote for '{ticker}'...")
        fundamentals_task = self.market.get_fundamentals(ticker)
        quote_task = self.market.get_quote(ticker)
        fundamentals, quote = await asyncio.gather(fundamentals_task, quote_task)

        company_name = (
            (fundamentals.company_name if fundamentals else None)
            or (quote.company_name if quote else None)
            or company_or_ticker.title()
        )
        logger.info(f"[DeepResearchService] Target Company Name: '{company_name}' ({ticker})")

        # Step 3: Multi-Angle Web Research
        search_queries = [
            f"{company_name} quarterly financial results earnings revenue profit",
            f"{company_name} competitive moat industry growth market share",
            f"{company_name} key risks headwinds regulatory challenges",
            f"{company_name} future catalysts capital expenditure strategic expansion",
        ]

        logger.info(f"[DeepResearchService] Conducting multi-angle web searches for '{company_name}' across {len(search_queries)} queries...")
        per_query_limit = max(2, settings.MAX_SEARCH_RESULTS // 2)
        search_tasks = [
            self.search_engine.search_news(q, max_results=per_query_limit, country=country)
            for q in search_queries[:2]
        ] + [
            self.search_engine.search(q, max_results=per_query_limit, country=country)
            for q in search_queries[2:]
        ]

        search_batches = await asyncio.gather(*search_tasks, return_exceptions=True)
        unique_citations: List[SourceCitation] = []
        seen_urls = set()

        for batch in search_batches:
            if isinstance(batch, list):
                for cit in batch:
                    if cit.url not in seen_urls:
                        seen_urls.add(cit.url)
                        unique_citations.append(cit)

        top_citations = unique_citations[:settings.MAX_SEARCH_RESULTS]
        for idx, c in enumerate(top_citations, start=1):
            c.id = idx
        logger.info(f"[DeepResearchService] Identified {len(top_citations)} unique citations for research grounding.")

        # Step 4: Parallel Scrape of Top Sources
        urls_to_scrape = [c.url for c in top_citations[:5]]
        logger.info(f"[DeepResearchService] Concurrently scraping {len(urls_to_scrape)} top URLs...")
        scraped_docs = await self.scraper.scrape_many(urls_to_scrape)
        
        extracted_contexts = []
        for doc in scraped_docs:
            if doc.success and doc.content:
                extracted_contexts.append(f"### Source: {doc.url}\n{doc.content[:2000]}")

        # Fallback to snippets if scraping is empty
        if not extracted_contexts:
            logger.info("[DeepResearchService] No complete document bodies extracted. Relying on search snippets.")
            extracted_contexts = [f"### Source: {c.title}\n{c.snippet}" for c in top_citations if c.snippet]

        web_context_text = "\n\n---\n\n".join(extracted_contexts)
        logger.debug(f"[DeepResearchService] Web intelligence context compiled ({len(web_context_text):,} chars).")

        # Step 5: Format Financial Fundamentals Context
        fundamentals_context = self._format_fundamentals_context(company_name, ticker, quote, fundamentals)

        # Step 6: Generate Research Report (Modular Sections vs Single Pass)
        if use_sectional:
            logger.info(f"[DeepResearchService] Generating report via MODULAR SECTION-BY-SECTION prompts...")
            markdown_report = await self._generate_section_by_section(
                company_name=company_name,
                ticker=ticker,
                created_time=created_time,
                country=country,
                fundamentals_context=fundamentals_context,
                web_context=web_context_text,
                temperature=settings.LLM_TEMPERATURE
            )
        else:
            logger.info(f"[DeepResearchService] Generating report via SINGLE-PASS cohesive prompt...")
            markdown_report = await self._generate_single_pass(
                company_name=company_name,
                ticker=ticker,
                created_time=created_time,
                country=country,
                fundamentals_context=fundamentals_context,
                web_context=web_context_text,
                temperature=settings.LLM_TEMPERATURE
            )

        # Extract executive summary preview
        exec_match = re.search(r"## 1\. Executive Summary.*?\n(.*?)(?=\n## 2|\Z)", markdown_report, re.DOTALL)
        exec_summary = exec_match.group(1).strip() if exec_match else f"Comprehensive equity research report for {company_name} ({ticker})."

        logger.info(f"[DeepResearchService] Research report compilation complete ({len(markdown_report):,} chars).")
        return DeepResearchResult(
            ticker=ticker,
            company_name=company_name,
            executive_summary=exec_summary,
            markdown_report=markdown_report,
            recommendation="Institutional Analysis",
            sources=top_citations,
            created_at=created_time,
            pdf_available=True
        )

    async def _generate_single_pass(
        self,
        company_name: str,
        ticker: str,
        created_time: str,
        country: str,
        fundamentals_context: str,
        web_context: str,
        temperature: float
    ) -> str:
        """Synthesizes the entire 7-section report in a single cohesive prompt."""
        report_prompt = f"""Target Company: {company_name} ({ticker})
Date of Report: {created_time}
Country: {country}

{fundamentals_context}

Extracted Web & Industry Intelligence:
{web_context or "No web articles extracted. Rely on fundamental metrics and market data provided above."}

Please synthesize an exhaustive, institutional Equity Research Report organized into the following mandatory sections:
## 1. Executive Summary & Investment Thesis
- High-level investment verdict (Overweight / Neutral / Underweight)
- Core thesis pillars (3-4 bullet points)
- Target price context and key catalysts

## 2. Company Profile & Core Business Model
- Operations, revenue segment breakdown, and key customer segments

## 3. Fundamental & Valuation Analysis
- Detailed evaluation of P/E, P/B, EPS, margins, and debt ratios
- Clean Markdown comparison table of key financial ratios
- Free cash flow generation and balance sheet resilience

## 4. Industry Dynamics & Competitive Moat
- Sector growth trends, regulatory environment, and barrier to entry
- Competitive advantages (pricing power, network effects, cost leadership)

## 5. Key Risk Factors
- Operational, regulatory, interest rate, and commodity price risks

## 6. Strategic Catalysts & Outlook
- Upcoming product launches, capacity additions, or market expansions

## 7. Valuation Conclusion & Rating Recommendation
- Bull, Base, and Bear case price targets or expected returns
- Final concluding verdict for investors
"""
        try:
            return await self.llm.generate_text(
                prompt=report_prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=temperature
            )
        except Exception as e:
            logger.error(f"[DeepResearchService] Error generating single-pass research report: {e}")
            return f"# Equity Research Report: {company_name} ({ticker})\n\nReport generation encountered an error: {str(e)}"

    async def _generate_section_by_section(
        self,
        company_name: str,
        ticker: str,
        created_time: str,
        country: str,
        fundamentals_context: str,
        web_context: str,
        temperature: float
    ) -> str:
        """
        Generates each of the 7 sections with dedicated, specialized prompts
        to maximize granularity, table depth, and analytical rigor.
        """
        sections_meta = [
            ("1. Executive Summary & Investment Thesis", "Synthesize a sharp executive summary, investment verdict (Overweight/Neutral/Underweight), target price expectations, and 3-4 core investment pillars."),
            ("2. Company Profile & Core Business Model", "Detail the company's operating divisions, revenue model, geographic split, manufacturing footprint, and core value proposition."),
            ("3. Fundamental & Valuation Analysis", f"Conduct an exhaustive financial ratio analysis. Include a structured Markdown table comparing P/E, P/B, EV/EBITDA, EPS, ROE, debt-to-equity, and free cash flow based on:\n{fundamentals_context}"),
            ("4. Industry Dynamics & Competitive Moat", "Analyze industry secular trends, market share dynamics, competitive rivalry, pricing power, and barriers to entry."),
            ("5. Key Risk Factors", "Examine critical operational risks, regulatory challenges, interest rate sensitivities, currency risks, and competitive threats."),
            ("6. Strategic Catalysts & Outlook", "Identify upcoming catalysts: capacity additions, product roadmap, expansion into new markets, margin turnaround triggers."),
            ("7. Valuation Conclusion & Rating Recommendation", "Provide Bull, Base, and Bear case valuation scenarios with estimated price targets and final institutional investment recommendation."),
        ]

        generated_sections = []
        for idx, (title, instruction) in enumerate(sections_meta, start=1):
            logger.info(f"[DeepResearchService] Generating Section {idx}/7: '{title}'...")
            section_prompt = f"""Target Company: {company_name} ({ticker})
Country: {country}
Date: {created_time}

Financial Context:
{fundamentals_context}

Web Intelligence:
{web_context[:2500] if web_context else 'Rely on company fundamentals.'}

TASK:
Write the complete Section: "## {title}".
Instructions: {instruction}

Focus solely on providing exhaustive, deeply researched content for this section in Markdown. Do not repeat titles of other sections.
"""
            try:
                content = await self.llm.generate_text(
                    prompt=section_prompt,
                    system_prompt=self.SYSTEM_PROMPT,
                    temperature=temperature
                )
                generated_sections.append(content.strip())
                logger.debug(f"[DeepResearchService] Section {idx}/7 completed ({len(content)} chars).")
            except Exception as e:
                logger.error(f"[DeepResearchService] Error generating section {title}: {e}")
                generated_sections.append(f"## {title}\n\nSection analysis temporarily unavailable: {str(e)}")

        combined_report = f"# Equity Research Report: {company_name} ({ticker})\n\n" + "\n\n".join(generated_sections)
        return combined_report

    def _format_fundamentals_context(
        self,
        name: str,
        ticker: str,
        quote: Optional[StockQuote],
        f: Optional[StockFundamentals]
    ) -> str:
        """Formats quote and balance sheet metrics for the LLM prompt."""
        lines = [f"### Fundamental Financial Data for {name} ({ticker}):"]
        if quote:
            lines.append(f"- Current Stock Price: {quote.currency} {quote.current_price:.2f} ({quote.change:+.2f} / {quote.change_percent:+.2f}%)")
            lines.append(f"- Day High/Low: {quote.day_low} - {quote.day_high}")
            lines.append(f"- 52-Week Range: {quote.year_low} - {quote.year_high}")

        if f:
            lines.append(f"- Sector: {f.sector or 'N/A'} | Industry: {f.industry or 'N/A'}")
            lines.append(f"- Market Cap: {f.market_cap or 'N/A'}")
            lines.append(f"- Trailing P/E Ratio: {f.pe_ratio or 'N/A'}")
            lines.append(f"- Price-to-Book (P/B): {f.pb_ratio or 'N/A'}")
            lines.append(f"- Trailing EPS: {f.eps or 'N/A'}")
            lines.append(f"- Return on Equity (ROE): {f.roe or 'N/A'}")
            lines.append(f"- Debt-to-Equity Ratio: {f.debt_to_equity or 'N/A'}")
            lines.append(f"- Total Revenue: {f.revenue or 'N/A'}")
            lines.append(f"- Net Income: {f.net_income or 'N/A'}")
            lines.append(f"- Free Cash Flow: {f.free_cash_flow or 'N/A'}")
            if f.financials:
                lines.append(f"- Margins: Operating {f.financials.get('operating_margins')}, Profit {f.financials.get('profit_margins')}")
        return "\n".join(lines)

    @staticmethod
    def export_pdf(markdown_content: str, company_name: str) -> bytes:
        """
        Converts Markdown research report into a professional PDF byte stream using ReportLab.
        Operates entirely in-memory with zero disk temporary files.
        """
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch
        )

        styles = getSampleStyleSheet()

        # Custom institutional typography styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=6
        )
        h2_style = ParagraphStyle(
            "DocH2",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=14,
            spaceAfter=6,
            keepWithNext=True
        )
        h3_style = ParagraphStyle(
            "DocH3",
            parent=styles["Heading3"],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#334155"),
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True
        )
        body_style = ParagraphStyle(
            "DocBody",
            parent=styles["BodyText"],
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#374151"),
            spaceAfter=6
        )
        bullet_style = ParagraphStyle(
            "DocBullet",
            parent=styles["BodyText"],
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#374151"),
            leftIndent=15,
            spaceAfter=3
        )

        story = []

        # Document Header Banner
        story.append(Paragraph(f"<b>MarketMind Institutional Research</b>", ParagraphStyle("HeaderSub", fontSize=10, textColor=colors.HexColor("#64748b"))))
        story.append(Paragraph(f"<b>Equity Research Report: {company_name}</b>", title_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=12))

        lines = markdown_content.split("\n")
        table_rows = []
        in_table = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                if in_table and table_rows:
                    # Flush table
                    t = Table(table_rows, hAlign="LEFT")
                    t.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ]))
                    story.append(t)
                    story.append(Spacer(1, 8))
                    table_rows = []
                    in_table = False
                continue

            # Markdown Table Row Detection
            if line.startswith("|") and line.endswith("|"):
                in_table = True
                cells = [c.strip() for c in line.split("|")[1:-1]]
                # Skip markdown separator row |---|---|
                if any(c.startswith("---") for c in cells):
                    continue
                row_paras = [Paragraph(c, body_style) for c in cells]
                table_rows.append(row_paras)
                continue
            elif in_table and table_rows:
                # Flush table before processing regular text
                t = Table(table_rows, hAlign="LEFT")
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ]))
                story.append(t)
                story.append(Spacer(1, 8))
                table_rows = []
                in_table = False

            # Convert markdown formatting to XML-safe tags
            clean_text = line
            # Escape raw & not in entities
            clean_text = re.sub(r"&(?!(amp|lt|gt|quot|apos);)", "&amp;", clean_text)
            # Replace bold markdown **text** with <b>text</b>
            clean_text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", clean_text)
            # Replace italics *text* with <i>text</i>
            clean_text = re.sub(r"(?<!\*)\*(?!\*)(.*?)\*(?!\*)", r"<i>\1</i>", clean_text)

            if clean_text.startswith("## "):
                story.append(Paragraph(clean_text[3:], h2_style))
            elif clean_text.startswith("### "):
                story.append(Paragraph(clean_text[4:], h3_style))
            elif clean_text.startswith(("- ", "* ", "• ")):
                story.append(Paragraph(f"&bull; {clean_text[2:]}", bullet_style))
            else:
                story.append(Paragraph(clean_text, body_style))

        # Final table flush if document ended with table
        if in_table and table_rows:
            t = Table(table_rows, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ]))
            story.append(t)

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        logger.info(f"[DeepResearchService] PDF successfully compiled: {len(pdf_bytes):,} bytes.")
        return pdf_bytes
