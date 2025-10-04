# /aigptssh/api/deep_research/views.py
import os
from fastapi import APIRouter, BackgroundTasks, Depends, Form
from api.security import api_key_auth
from .research_pipeline import run_deep_research
from .stock_research_pipeline import StockResearchPipeline

router = APIRouter()

@router.post("/")
async def start_deep_research(
    background_tasks: BackgroundTasks,
    query: str = Form(...),
    is_stock_analysis: bool = Form(False),
    api_key: str = Depends(api_key_auth)
):
    """
    Kicks off a deep research task in the background.
    """
    if is_stock_analysis:
        # Use the new stock analysis pipeline
        pipeline = StockResearchPipeline(query)
        
        async def run_stock_pipeline():
            pdf_bytes = await pipeline.run()
            if pdf_bytes:
                # Sanitize the filename
                safe_filename = "".join(c for c in query if c.isalnum() or c in (' ', '_')).rstrip()
                output_filename = f"{safe_filename}_Stock_Analysis.pdf".replace(" ", "_")
                output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_filename)
                
                with open(output_path, "wb") as f:
                    f.write(pdf_bytes)
                print(f"SUCCESS: Stock analysis report saved to {output_path}")
            else:
                print("FAILURE: The stock research pipeline did not produce a PDF.")

        background_tasks.add_task(run_stock_pipeline)
        return {
            "message": f"Comprehensive stock analysis for '{query}' has been started. The PDF report will be generated in the background."
        }
    else:
        # Use the existing general research pipeline
        background_tasks.add_task(run_deep_research, query)
        return {
            "message": f"Deep research task for '{query}' has been started. The PDF report will be generated in the background."
        }