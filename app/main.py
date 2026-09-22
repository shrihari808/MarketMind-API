"""
MarketMind Intelligence API v2.
High-Performance Financial RAG, Real-Time Market Intelligence & Multimodal Analytics Engine.
Clean Architecture, SOLID principles, and strict 512 MB RAM footprint.
"""

import os
import sys
import time

# Enforce single-thread BLAS/math execution to eliminate OpenBLAS memory retry errors
# and guarantee low memory footprint (<512 MB RAM) on Windows and cloud hosts
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.core.logging import logger
from app.core.rate_limiter import IPRateLimitMiddleware
from app.api.v2.router import api_v2_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown events.
    Initializes database tables and releases connection pools cleanly.
    """
    logger.info("Initializing MarketMind API v2 application...")
    await init_db()
    logger.info("MarketMind API v2 startup complete. Ready for requests.")
    yield
    logger.info("Shutting down MarketMind API v2 application...")
    await close_db()
    logger.info("MarketMind API v2 shutdown complete.")


# Initialize FastAPI application
settings = get_settings()
app = FastAPI(
    title="MarketMind Intelligence API v2",
    version="2.0.0",
    description=(
        "Institutional-grade Financial Intelligence API featuring streaming Web RAG, "
        "native Multimodal Document analysis, Reddit community sentiment, "
        "real-time market dashboards (SWR cached), and deep equity research PDF generation."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# --- 1. IP Rate Limiting Middleware (25 req/min) ---
app.add_middleware(IPRateLimitMiddleware)

# --- 2. CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


# --- 3. Request Timing & Process Monitoring Middleware ---
@app.middleware("http")
async def process_time_middleware(request: Request, call_next):
    start_time = time.time()
    response: Response = await call_next(request)
    duration = time.time() - start_time
    response.headers["X-Process-Time"] = f"{duration:.3f}s"
    return response


# --- 4. Global Exception Handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"[GlobalException] Unhandled error during request to {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if settings.DEBUG else "An unexpected server error occurred."
        }
    )


# --- 5. Mount API v2 Master Router ---
app.include_router(api_v2_router)


# --- 6. Mount Frontend Static Distribution (Hybrid Host Support) ---
frontend_dist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
frontend_assets_dir = os.path.join(frontend_dist_dir, "assets")

if os.path.exists(frontend_assets_dir):
    from fastapi.staticfiles import StaticFiles
    app.mount("/assets", StaticFiles(directory=frontend_assets_dir), name="frontend-assets")


# --- 7. Root Landing Endpoint ---
@app.get("/", tags=["Root"], summary="MarketMind v2 API Gateway Welcome & Web Terminal")
async def root_gateway(request: Request):
    accept_header = request.headers.get("accept", "")
    index_file = os.path.join(frontend_dist_dir, "index.html")

    # If browser requests HTML and frontend distribution is built, serve the web terminal
    if "text/html" in accept_header and os.path.exists(index_file):
        from fastapi.responses import FileResponse
        return FileResponse(index_file)

    return {
        "service": "MarketMind Intelligence API",
        "version": "2.0.0",
        "status": "online",
        "documentation": "/docs",
        "v2_endpoints": "/api/v2",
        "architecture": "Clean Architecture & SOLID",
        "memory_optimized": True
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

