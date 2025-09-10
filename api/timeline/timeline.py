# aigptssh/api/timeline/timeline.py
import os
import time
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from api.security import api_key_auth

router = APIRouter()

# --- Define Paths ---
TIMELINE_DIR = os.path.dirname(os.path.abspath(__file__))
TIMELINE_JSON_PATH = os.path.join(TIMELINE_DIR, 'timeline.json')

@router.get("/timeline")
async def get_timeline(api_key: str = Depends(api_key_auth)):
    """
    Retrieves the generated timeline of financial news.
    The timeline is updated periodically by a background scheduler.
    """
    if not os.path.exists(TIMELINE_JSON_PATH):
        raise HTTPException(
            status_code=404,
            detail="Timeline data not found. It may still be generating."
        )

    #Optional: Check file age to provide a 'last updated' header or similar
    file_mod_time = os.path.getmtime(TIMELINE_JSON_PATH)
    if (time.time() - file_mod_time) > (6 * 3600 + 600): # 6 hours + 10 min buffer
        # This could indicate the scheduler has an issue
        print("WARNING: Timeline data is older than expected.")

    return FileResponse(TIMELINE_JSON_PATH)
