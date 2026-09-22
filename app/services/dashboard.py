"""
Market Dashboard Service with Stale-While-Revalidate (SWR) Caching.
Replaces resource-heavy 24/7 background daemons with on-demand SWR caching in the database.
Supports runtime configuration for active/inactive toggle and hourly TTL.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import select
from app.core.config import get_settings
from app.core.database import async_session_factory, DashboardCacheRecord
from app.core.logging import logger
from app.domain.interfaces.llm import LLMClient
from app.domain.interfaces.market import MarketDataClient
from app.domain.schemas.market import MarketDashboardSnapshot
from app.infrastructure.llm.gemini import GeminiLLMClient
from app.infrastructure.market.yfinance_client import YFinanceMarketClient


class MarketDashboardService:
    """Service providing on-demand market snapshots with Stale-While-Revalidate (SWR)."""

    def __init__(
        self,
        market_client: Optional[MarketDataClient] = None,
        llm_client: Optional[LLMClient] = None
    ):
        self.market = market_client or YFinanceMarketClient()
        self.llm = llm_client or GeminiLLMClient()
        self.settings = get_settings()

    @property
    def is_enabled(self) -> bool:
        """Returns whether the dashboard service is active in settings."""
        return self.settings.DASHBOARD_ENABLED

    @property
    def ttl_seconds(self) -> float:
        """Returns the cache TTL in seconds based on DASHBOARD_CACHE_TTL_HOURS."""
        return max(60.0, float(self.settings.DASHBOARD_CACHE_TTL_HOURS) * 3600.0)

    async def _generate_fresh_snapshot(self, country: str = "IN") -> MarketDashboardSnapshot:
        """Fetches live market data and synthesizes a daily market commentary."""
        logger.info(f"Generating fresh market dashboard snapshot for country: {country}...")
        
        # Concurrently fetch indices and top movers
        indices_task = self.market.get_market_indices(country)
        movers_task = self.market.get_top_movers(country)

        indices, movers = await asyncio.gather(indices_task, movers_task)
        gainers = movers.get("gainers", [])
        losers = movers.get("losers", [])

        # Build context for Gemini macro market brief
        indices_summary = ", ".join([f"{idx.name}: {idx.price} ({idx.change_percent:+.2f}%)" for idx in indices])
        gainers_summary = ", ".join([f"{g.name}: {g.change_percent:+.2f}%" for g in gainers])
        losers_summary = ", ".join([f"{l.name}: {l.change_percent:+.2f}%" for l in losers])

        prompt = (
            f"You are a senior market analyst. Synthesize a concise 2-paragraph market brief for {country} based on today's performance:\n"
            f"- Major Indices: {indices_summary}\n"
            f"- Top Gainers: {gainers_summary}\n"
            f"- Top Losers: {losers_summary}\n\n"
            f"Provide an objective commentary highlighting dominant sectors, overall sentiment, and key drivers."
        )

        logger.info(f"[MarketDashboardService] Fetched {len(indices)} indices, {len(gainers)} gainers, {len(losers)} losers for country: {country}.")

        try:
            logger.info(f"[MarketDashboardService] Generating macro market brief via Gemini (temp={self.settings.LLM_TEMPERATURE})...")
            sentiment_commentary = await self.llm.generate_text(
                prompt=prompt,
                system_prompt="You are MarketMind, an institutional financial market intelligence assistant.",
                temperature=self.settings.LLM_TEMPERATURE
            )
        except Exception as e:
            logger.warning(f"[MarketDashboardService] LLM synthesis failed for dashboard brief ({e}). Using rule-based fallback.")
            sentiment_commentary = (
                f"Markets closed with mixed performance across sectors. "
                f"Major indices recorded: {indices_summary}."
            )

        snapshot = MarketDashboardSnapshot(
            country=country.upper(),
            indices=indices,
            top_gainers=gainers,
            top_losers=losers,
            market_sentiment=sentiment_commentary,
            updated_at=datetime.now(timezone.utc)
        )
        return snapshot

    async def _save_to_cache(self, country: str, snapshot: MarketDashboardSnapshot) -> None:
        """Persists or updates the snapshot in the database."""
        country_code = country.upper()
        data_str = snapshot.model_dump_json()

        try:
            async with async_session_factory() as session:
                query = select(DashboardCacheRecord).where(DashboardCacheRecord.country == country_code)
                result = await session.execute(query)
                record = result.scalar_one_or_none()

                if record:
                    record.data_json = data_str
                    record.updated_at = datetime.utcnow()
                else:
                    record = DashboardCacheRecord(
                        country=country_code,
                        data_json=data_str,
                        updated_at=datetime.utcnow()
                    )
                    session.add(record)

                await session.commit()
                logger.info(f"Dashboard snapshot for {country_code} cached in database.")
        except Exception as e:
            logger.error(f"Error persisting dashboard cache to database: {e}")

    async def revalidate_cache(self, country: str = "IN") -> MarketDashboardSnapshot:
        """Generates a fresh snapshot and asynchronously saves it to database."""
        snapshot = await self._generate_fresh_snapshot(country)
        await self._save_to_cache(country, snapshot)
        return snapshot

    async def get_snapshot(
        self,
        country: str = "IN",
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Retrieves the dashboard snapshot using Stale-While-Revalidate (SWR).
        Returns instantly from cache if fresh, or triggers async revalidation if stale.
        """
        # Step 0: Check if dashboard service is enabled
        if not self.is_enabled:
            logger.info("Market dashboard service is disabled via DASHBOARD_ENABLED=False.")
            return {
                "enabled": False,
                "message": "Market dashboard service is currently inactive / disabled in configuration.",
                "data": None
            }

        country_code = country.upper()

        if force_refresh:
            snapshot = await self.revalidate_cache(country_code)
            return {"enabled": True, "stale": False, "data": snapshot.model_dump()}

        # Step 1: Query database cache
        cached_record: Optional[DashboardCacheRecord] = None
        try:
            async with async_session_factory() as session:
                query = select(DashboardCacheRecord).where(DashboardCacheRecord.country == country_code)
                result = await session.execute(query)
                cached_record = result.scalar_one_or_none()
        except Exception as e:
            logger.warning(f"Failed to read dashboard cache from database ({e}). Proceeding to generate fresh.")

        # Step 2: Evaluate Cache Freshness
        if cached_record and cached_record.data_json:
            now_utc = datetime.utcnow()
            record_age_seconds = (now_utc - cached_record.updated_at).total_seconds()
            cached_data = json.loads(cached_record.data_json)

            if record_age_seconds < self.ttl_seconds:
                # Fresh cache hit
                logger.debug(f"Dashboard cache HIT (fresh, age: {record_age_seconds:.0f}s / TTL: {self.ttl_seconds:.0f}s)")
                return {"enabled": True, "stale": False, "data": cached_data}
            else:
                # Stale cache hit: Return stale data immediately, revalidate in background
                logger.info(
                    f"Dashboard cache STALE (age: {record_age_seconds:.0f}s > TTL: {self.ttl_seconds:.0f}s). "
                    f"Serving stale data and revalidating in background."
                )
                asyncio.create_task(self.revalidate_cache(country_code))
                return {"enabled": True, "stale": True, "data": cached_data}

        # Step 3: Cache Miss (First run)
        logger.info(f"Dashboard cache MISS for {country_code}. Generating synchronously...")
        snapshot = await self.revalidate_cache(country_code)
        return {"enabled": True, "stale": False, "data": snapshot.model_dump()}
