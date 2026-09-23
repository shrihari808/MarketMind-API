"""
Market Dashboard Service with Stale-While-Revalidate (SWR) Caching.
Replaces resource-heavy 24/7 background daemons with on-demand SWR caching in the database.
Supports runtime configuration for active/inactive toggle and hourly TTL.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.core.config import get_settings
from app.core.database import async_session_factory, DashboardCacheRecord
from app.core.logging import logger
from app.domain.interfaces.llm import LLMClient
from app.domain.interfaces.market import MarketDataClient
from app.domain.schemas.market import MarketDashboardSnapshot, PromptSuggestion
from app.infrastructure.llm.gemini import GeminiLLMClient
from app.infrastructure.market.yfinance_client import YFinanceMarketClient


class DashboardSynthesis(BaseModel):
    """Structured response schema for LLM dashboard commentary and prompt suggestions."""
    market_sentiment: str = Field(
        description="A concise 2-paragraph market brief for the country based on today's performance, highlighting dominant sectors, overall sentiment, and key drivers."
    )
    prompt_suggestions: List[PromptSuggestion] = Field(
        description="Exactly 4 timely, highly relevant research prompt suggestions based on today's market performance, indices, and top movers."
    )


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

    def _generate_fallback_prompts(
        self,
        country: str,
        indices: list,
        gainers: list,
        losers: list
    ) -> List[PromptSuggestion]:
        """Generates dynamic fallback prompt suggestions based on movers and indices."""
        country_code = country.upper()
        suggestions: List[PromptSuggestion] = []

        # 1. Top Gainer prompt
        if gainers:
            g = gainers[0]
            g_name = getattr(g, "name", None) or (g.get("name") if isinstance(g, dict) else "") or "Top Gainer"
            g_ticker = getattr(g, "ticker", None) or (g.get("ticker") if isinstance(g, dict) else "") or ""
            short_name = g_name.split()[0] if g_name else g_ticker
            header = f"{short_name} Rally"
            display_stock = f"{g_name} ({g_ticker})" if g_ticker else g_name
            prompt = f"What is driving the recent rally in {display_stock} and what is the near-term valuation outlook?"
            suggestions.append(PromptSuggestion(header=header, prompt=prompt))

        # 2. Top Loser prompt
        if losers:
            l = losers[0]
            l_name = getattr(l, "name", None) or (l.get("name") if isinstance(l, dict) else "") or "Top Loser"
            l_ticker = getattr(l, "ticker", None) or (l.get("ticker") if isinstance(l, dict) else "") or ""
            short_name = l_name.split()[0] if l_name else l_ticker
            header = f"{short_name} Drop"
            display_stock = f"{l_name} ({l_ticker})" if l_ticker else l_name
            prompt = f"Analyze the key factors behind the decline in {display_stock} and assess the primary downside risks."
            suggestions.append(PromptSuggestion(header=header, prompt=prompt))

        # 3. Leading Index prompt
        if indices:
            idx = indices[0]
            idx_name = getattr(idx, "name", None) or (idx.get("name") if isinstance(idx, dict) else "") or "Market Index"
            header = f"{idx_name} Trend"
            prompt = f"What macroeconomic catalysts and sector rotation trends are impacting {idx_name} today?"
            suggestions.append(PromptSuggestion(header=header, prompt=prompt))

        # 4. Standard high-relevance defaults based on country
        if country_code == "IN":
            defaults = [
                PromptSuggestion(header="Tata Motors EV", prompt="What is Tata Motors valuation outlook and domestic EV market share?"),
                PromptSuggestion(header="Reliance Capex", prompt="Analyze Reliance Industries capex, retail expansion, and net debt levels."),
                PromptSuggestion(header="HDFC Bank Margins", prompt="What is the latest NIM margin trend and credit growth outlook for HDFC Bank?"),
                PromptSuggestion(header="Nifty IT Sector", prompt="Analyze the valuation multiples and earnings growth outlook for Indian IT majors.")
            ]
        else:
            defaults = [
                PromptSuggestion(header="Nvidia Blackwell", prompt="What is the demand outlook for Nvidia Blackwell AI chips and data center capex?"),
                PromptSuggestion(header="Apple Services", prompt="Analyze Apple Services revenue growth, margins, and ecosystem moat."),
                PromptSuggestion(header="S&P 500 Fed Cuts", prompt="How will Federal Reserve interest rate policy impact the S&P 500 tech sector?"),
                PromptSuggestion(header="Cloud Capex ROI", prompt="Evaluate cloud capex trends and AI infrastructure returns for Microsoft, Google, and Amazon.")
            ]

        # Combine mover-based suggestions with defaults to ensure exactly 4 unique prompts
        for item in defaults:
            if len(suggestions) >= 4:
                break
            if not any(s.header.lower() == item.header.lower() for s in suggestions):
                suggestions.append(item)

        return suggestions[:4]

    async def _generate_fresh_snapshot(self, country: str = "IN") -> MarketDashboardSnapshot:
        """Fetches live market data and synthesizes a daily market commentary along with dynamic prompt suggestions."""
        logger.info(f"Generating fresh market dashboard snapshot for country: {country}...")
        
        # Concurrently fetch indices and top movers
        indices_task = self.market.get_market_indices(country)
        movers_task = self.market.get_top_movers(country)

        indices, movers = await asyncio.gather(indices_task, movers_task)
        gainers = movers.get("gainers", [])
        losers = movers.get("losers", [])

        # Build context for Gemini macro market brief and suggestions
        indices_summary = ", ".join([f"{idx.name}: {idx.price} ({idx.change_percent:+.2f}%)" for idx in indices])
        gainers_summary = ", ".join([f"{g.name}: {g.change_percent:+.2f}%" for g in gainers])
        losers_summary = ", ".join([f"{l.name}: {l.change_percent:+.2f}%" for l in losers])

        prompt = (
            f"You are a senior market analyst and institutional research director.\n"
            f"Synthesize today's market performance for {country}:\n"
            f"- Major Indices: {indices_summary}\n"
            f"- Top Gainers: {gainers_summary}\n"
            f"- Top Losers: {losers_summary}\n\n"
            f"Requirements:\n"
            f"1. market_sentiment: A concise 2-paragraph market brief highlighting dominant sectors, overall sentiment, and key drivers.\n"
            f"2. prompt_suggestions: Exactly 4 dynamic, timely prompt suggestions for an investor exploring today's market action.\n"
            f"   Each suggestion must have:\n"
            f"   - 'header': A punchy 2-4 word label (e.g. 'Nifty IT Rally', 'Tata Motors Capex', 'Tech Sector Rebound')\n"
            f"   - 'prompt': A comprehensive, insightful prompt question to ask our AI financial assistant."
        )

        logger.info(f"[MarketDashboardService] Fetched {len(indices)} indices, {len(gainers)} gainers, {len(losers)} losers for country: {country}.")

        sentiment_commentary = ""
        prompt_suggestions: List[PromptSuggestion] = []

        try:
            logger.info(f"[MarketDashboardService] Generating macro market brief and structured prompt suggestions via Gemini...")
            synthesis = await self.llm.generate_structured(
                prompt=prompt,
                response_schema=DashboardSynthesis,
                system_prompt="You are MarketMind, an institutional financial market intelligence assistant."
            )
            sentiment_commentary = synthesis.market_sentiment
            prompt_suggestions = [
                p for p in (synthesis.prompt_suggestions or [])
                if p.header and p.header.strip() and p.prompt and p.prompt.strip()
            ]
        except Exception as e:
            logger.warning(f"[MarketDashboardService] Structured LLM synthesis failed for dashboard ({e}). Using rule-based fallback.")

        if not sentiment_commentary:
            sentiment_commentary = (
                f"Markets closed with mixed performance across sectors. "
                f"Major indices recorded: {indices_summary}."
            )

        # Ensure exactly 4 suggestions are returned using fallbacks if needed
        if len(prompt_suggestions) < 4:
            fallbacks = self._generate_fallback_prompts(country, indices, gainers, losers)
            for fb in fallbacks:
                if len(prompt_suggestions) >= 4:
                    break
                if not any(p.header.lower() == fb.header.lower() for p in prompt_suggestions):
                    prompt_suggestions.append(fb)
            prompt_suggestions = prompt_suggestions[:4]

        snapshot = MarketDashboardSnapshot(
            country=country.upper(),
            indices=indices,
            top_gainers=gainers,
            top_losers=losers,
            market_sentiment=sentiment_commentary,
            prompt_suggestions=prompt_suggestions,
            updated_at=datetime.now(timezone.utc)
        )
        return snapshot

    async def _save_to_cache(self, country: str, snapshot: MarketDashboardSnapshot) -> None:
        """Persists or updates the snapshot in the database."""
        country_code = country.upper()

        # Safeguard: do not persist empty or all-zero snapshots to cache
        valid_indices = [idx for idx in snapshot.indices if idx.price > 0]
        if not valid_indices:
            logger.warning(f"Refusing to save all-zero dashboard snapshot to cache for {country_code}")
            return

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
            cached_indices = cached_data.get("indices", [])
            has_valid_indices = any(idx.get("price", 0) > 0 for idx in cached_indices)

            if not has_valid_indices:
                logger.warning(
                    f"Dashboard cache for {country_code} contained zeroed index quotes. Forcing fresh regeneration..."
                )
                snapshot = await self.revalidate_cache(country_code)
                return {"enabled": True, "stale": False, "data": snapshot.model_dump()}

            if not cached_data.get("prompt_suggestions") or len(cached_data.get("prompt_suggestions", [])) < 4:
                cached_data["prompt_suggestions"] = [
                    p.model_dump() for p in self._generate_fallback_prompts(
                        country_code,
                        cached_data.get("indices", []),
                        cached_data.get("top_gainers", []),
                        cached_data.get("top_losers", [])
                    )
                ]

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
