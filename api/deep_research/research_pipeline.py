# /aigptssh/api/deep_research/research_pipeline.py
import asyncio
import os
import fitz  # PyMuPDF
from api.brave_searcher import BraveNews
from api.dashboard.web_scraper import scrape_urls
from api.news_rag.scoring_service import NewsRagScoringService
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Use Gemini 2.5 Pro as the LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.2)

class DeepResearchPipeline:
    def __init__(self, query: str):
        self.query = query
        self.brave_searcher = BraveNews(os.getenv("BRAVE_API_KEY"))
        self.scoring_service = NewsRagScoringService()

    async def run(self):
        # 1. Information Gathering
        print("Step 1: Gathering initial sources...")
        search_results = await self.brave_searcher.search_and_scrape(self.query, max_sources=20)

        # 2. Scraping
        print("Step 2: Scraping top sources...")
        scraped_articles = await scrape_urls(search_results)

        # 3. Content Synthesis
        print("Step 3: Synthesizing content...")
        full_text = "\n\n---\n\n".join([article.get('content', '') for article in scraped_articles if article.get('content')])
        report_text = await self.generate_report_text(full_text)

        # 4. PDF Generation
        print("Step 4: Generating PDF...")
        pdf_buffer = self.create_pdf_from_text(report_text)

        return pdf_buffer

    async def generate_report_text(self, context: str) -> str:
        """Uses an LLM to generate a structured research report."""
        template = """
        You are a professional research analyst. Based on the provided context, write a comprehensive, well-structured research report on the following topic: "{query}"

        The report should include:
        1.  **Executive Summary:** A brief overview of the key findings.
        2.  **Introduction:** Background on the topic.
        3.  **Main Body:** A detailed analysis with several sections covering different aspects of the topic. Use the context provided.
        4.  **Conclusion:** A summary of the main points and a concluding thought.

        Context:
        {context}
        """
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | llm | StrOutputParser()

        response = await chain.ainvoke({"query": self.query, "context": context})
        return response

    def create_pdf_from_text(self, text: str) -> bytes:
        """Creates a simple PDF from a string of text using PyMuPDF."""
        doc = fitz.open()  # New PDF
        page = doc.new_page()

        # Simple text insertion with basic formatting
        rect = page.rect + (50, 50, -50, -50)  # Margin
        page.insert_textbox(rect, text, fontsize=11, fontname="helv", align=fitz.TEXT_ALIGN_LEFT)

        # Save to a byte buffer
        pdf_buffer = doc.write()
        doc.close()
        return pdf_buffer

async def run_deep_research(query: str):
    pipeline = DeepResearchPipeline(query)
    pdf_bytes = await pipeline.run()
    output_path = f"deep_research_report_{query[:20].replace(' ', '_')}.pdf"
    with open(output_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"Report saved to {output_path}")