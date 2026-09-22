"""
MarketMind API v2 Application Root Entrypoint.
Delegates to the modernized Clean Architecture application in app.main.
Supports `uvicorn main:app --reload` and direct `python main.py` execution.
"""

import os
import sys

# Prevent OpenBLAS memory allocation retry issues on Windows & cloud containers
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))

# Expose the modern v2 FastAPI app instance
from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)