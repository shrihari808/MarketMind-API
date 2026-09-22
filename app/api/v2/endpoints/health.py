"""
Health Check and System Readiness Endpoint for MarketMind API v2.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import get_settings
from app.api.deps import get_db

router = APIRouter(tags=["Health & Status"])


@router.get("/health", summary="System Health & Readiness Check")
async def health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns API version, system status, active providers, and verifies database connectivity.
    """
    settings = get_settings()

    # Check database connectivity
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy ({str(e)})"

    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "api_name": "MarketMind Intelligence API",
        "version": "2.0.0",
        "database": db_status,
        "search_provider": settings.SEARCH_PROVIDER,
        "gemini_model": settings.GEMINI_MODEL,
        "rate_limiting": {
            "enabled": settings.RATE_LIMIT_ENABLED,
            "max_per_minute": settings.RATE_LIMIT_PER_MINUTE
        }
    }
