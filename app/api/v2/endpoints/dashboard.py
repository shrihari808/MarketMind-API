"""
Market Overview Dashboard Endpoint with Stale-While-Revalidate (SWR) Caching.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_dashboard_service
from app.services.dashboard import MarketDashboardService

router = APIRouter(prefix="/dashboard", tags=["Market Dashboard"])


@router.get(
    "",
    summary="Get Real-Time Market Indices, Trending Movers & Macro AI Brief"
)
async def get_market_dashboard(
    country: str = Query(default="IN", description="Country market context (e.g. 'IN', 'US')"),
    force_refresh: bool = Query(default=False, description="Bypass cache and force fresh data generation"),
    dashboard_service: MarketDashboardService = Depends(get_dashboard_service)
) -> Dict[str, Any]:
    """
    Returns live benchmark indices (Nifty, Sensex, S&P 500, Nasdaq), standout gainers and losers,
    and an AI-synthesized macroeconomic commentary.
    Backed by on-demand Stale-While-Revalidate (SWR) caching with configurable TTL and zero background daemons.
    """
    return await dashboard_service.get_snapshot(country=country, force_refresh=force_refresh)
