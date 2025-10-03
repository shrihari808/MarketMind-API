# /aigptssh/api/deep_research/research_pipeline.py
import asyncio
import os
import aiohttp
from io import BytesIO
from api.brave_searcher import BraveNews
from api.dashboard.web_scraper import scrape_urls
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# --- Import ReportLab ---
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# Use Gemini 2.5 Pro as the LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0.2)

class DeepResearchPipeline:
    def __init__(self, query: str):
        self.query = query
        self.brave_searcher = BraveNews(os.getenv("BRAVE_API_KEY"))

    async def run(self):
        async with aiohttp.ClientSession(**self.brave_searcher.session_config) as session:
            print("Step 1: Gathering initial sources...")
            search_results = await self.brave_searcher.search_and_scrape(session, self.query, max_sources=20)
            if not search_results:
                print("Error: No search results found. Halting pipeline.")
                return None

            print(f"Step 2: Scraping top {len(search_results)} sources...")
            scraped_articles = await scrape_urls(search_results)
            if not scraped_articles:
                print("Error: Failed to scrape any content. Halting pipeline.")
                return None

            print("Step 3: Synthesizing content for LLM...")
            full_text = "\n\n---\n\n".join([article.get('content', '') for article in scraped_articles if article.get('content')])
            if not full_text:
                print("Error: No text content was extracted from sources. Halting pipeline.")
                return None

            print(f"Generated a context of {len(full_text)} characters for the report.")
            report_text = await self.generate_report_text(full_text)

            print(f"Step 3.5: LLM generated report of {len(report_text)} characters.")
            if not report_text.strip():
                print("Error: LLM returned an empty or whitespace-only report. Halting pipeline.")
                return None

            print("Step 4: Generating PDF from report text...")
            pdf_buffer = self.create_pdf_from_text(report_text)
            return pdf_buffer

    async def generate_report_text(self, context: str) -> str:
        """Uses an LLM to generate a structured research report."""
        template = """
        You are a professional financial research analyst. Based on the provided context, write a comprehensive, well-structured research report on the following topic: "{query}"

        The report should include:
        1.  **Executive Summary:** A brief overview of the key findings.
        2.  **Introduction:** Background on the topic.
        3.  **Main Body:** A detailed analysis with several sections covering different aspects of the topic. Use the context provided.
        4.  **Conclusion:** A summary of the main points and a concluding thought.
        
        Use markdown for formatting headers (e.g., ## Header) and lists (e.g., * item).
        Context:
        {context}
        """
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | llm | StrOutputParser()

        response = await chain.ainvoke({"query": self.query, "context": context})
        return response

    def create_pdf_from_text(self, text: str) -> bytes:
        """Creates a PDF from a markdown-formatted string using reportlab."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch)
        styles = getSampleStyleSheet()
        story = []

        # Replace markdown-like headers with simple bold text for the PDF
        text = text.replace("## ", "").replace("**", "")

        # Split the text into paragraphs and add them to the story
        for paragraph in text.split('\n'):
            if paragraph.strip():  # Avoid adding empty paragraphs
                p = Paragraph(paragraph, styles['Normal'])
                story.append(p)
                story.append(Spacer(1, 0.2 * inch)) # Add some space after each paragraph

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

async def run_deep_research(query: str):
    try:
        pipeline = DeepResearchPipeline(query)
        pdf_bytes = await pipeline.run()

        if pdf_bytes:
            # Get the directory of the current file (api/deep_research/)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Set the output path to 'output.pdf' inside that directory
            output_path = os.path.join(current_dir, 'output.pdf')
            
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
            print(f"SUCCESS: Report saved to {output_path}")
        else:
            print("FAILURE: The research pipeline did not produce a PDF.")
    except Exception as e:
        print(f"FATAL ERROR in research pipeline: {e}")