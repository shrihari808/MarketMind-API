"""
Health Check and System Readiness Endpoint for MarketMind API v2.
Includes runtime rate-limit inspection and configuration endpoints.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import get_settings
from app.core.rate_limiter import rate_limiter
from app.api.deps import get_db

router = APIRouter(tags=["Health & Status"])


class RateLimitConfigRequest(BaseModel):
    """Payload for dynamically configuring or toggling the rate limiter at runtime."""
    enabled: Optional[bool] = Field(default=None, description="Toggle rate limiting on (True) or off (False)")
    limit_per_minute: Optional[int] = Field(default=None, ge=1, le=1000, description="New requests per minute threshold")
    reset_history: bool = Field(default=False, description="Clear active IP sliding window request counters")


@router.api_route("/health", methods=["GET", "HEAD"], summary="System Health & Readiness Check")
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
            "enabled": rate_limiter.is_enabled,
            "max_per_minute": rate_limiter.limit_per_minute
        }
    }


@router.api_route("/health/rate-limit", methods=["GET", "HEAD"], summary="Inspect Active Rate Limit Configuration")
async def get_rate_limit_config() -> Dict[str, Any]:
    """
    Returns current rate limiting state: whether active and current requests-per-minute threshold.
    """
    return {
        "enabled": rate_limiter.is_enabled,
        "limit_per_minute": rate_limiter.limit_per_minute,
        "window_seconds": rate_limiter.window_seconds
    }


@router.post("/health/rate-limit", summary="Dynamically Toggle or Configure Rate Limit at Runtime")
async def configure_rate_limit(config: RateLimitConfigRequest) -> Dict[str, Any]:
    """
    Allows developers or operators to toggle rate limiting on/off, change the threshold
    (requests per minute), or clear active IP history without restarting the application.
    """
    if config.enabled is not None:
        rate_limiter.set_enabled(config.enabled)
    if config.limit_per_minute is not None:
        rate_limiter.set_limit(config.limit_per_minute)
    if config.reset_history:
        rate_limiter.reset()

    return {
        "message": "Rate limiter configuration updated successfully.",
        "enabled": rate_limiter.is_enabled,
        "limit_per_minute": rate_limiter.limit_per_minute,
        "window_seconds": rate_limiter.window_seconds
    }
