# /aigptssh/api/deep_research/router.py
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from api.security import api_key_auth
from .research_pipeline import run_deep_research
import os # <-- Add os import

router = APIRouter()

class DeepResearchRequest(BaseModel):
    query: str

@router.post("/") # <-- Changed path to "/" to be prefixed by the main router
async def start_deep_research(
    request: DeepResearchRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(api_key_auth)
):
    """
    Kicks off a deep research task in the background.
    """
    background_tasks.add_task(run_deep_research, request.query)
    # The response now includes a hint about where to find the generated file
    return {
        "message": f"Deep research task for '{request.query}' has been started. The PDF report will be generated in the background in the project's root directory."
    }