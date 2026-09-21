"""
Financial Query Analyzer Service.
Validates financial intent, decomposes queries into targeted sub-queries,
detects stock tickers, resolves exchange symbols, and reformulates follow-up questions.
"""

import re
from datetime import datetime, timezone
from typing import List, Optional, Dict
from app.core.logging import logger
from app.domain.interfaces.llm import LLMClient
from app.domain.interfaces.market import MarketDataClient
from app.domain.schemas.rag import QueryAnalysisResult
from app.infrastructure.llm.gemini import GeminiLLMClient
from app.infrastructure.market.yfinance_client import YFinanceMarketClient


class QueryAnalyzer:
    """Async query analyzer for financial intelligence workflows."""

    # Common financial keywords for rapid heuristic fallback
    FINANCIAL_KEYWORDS = {
        "stock", "share", "equity", "market", "nifty", "sensex", "nasdaq", "s&p",
        "dividend", "earnings", "q1", "q2", "q3", "q4", "revenue", "profit", "ebitda",
        "pe ratio", "p/e", "eps", "ipo", "invest", "portfolio", "yield", "bond",
        "inflation", "interest rate", "fed", "rbi", "bull", "bear", "rally", "crash",
        "price", "valuation", "target", "guidance", "balance sheet", "debt", "cash flow"
    }

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        market_client: Optional[MarketDataClient] = None
    ):
        self.llm = llm_client or GeminiLLMClient()
        self.market = market_client or YFinanceMarketClient()

    def _is_followup_question(self, query: str, chat_history: Optional[List[Dict[str, str]]]) -> bool:
        """Determines if the query relies on preceding conversation context."""
        if not chat_history:
            return False

        followup_patterns = [
            r"\b(it|this|that|they|them|its|their|the company|the stock)\b",
            r"\b(what about|how about|tell me more|and what|why did this happen)\b",
            r"\b(compared to|versus|vs\.?|difference)\b",
            r"^\b(why|how|when|where|who)\b",
        ]
        query_lower = query.lower().strip()
        for pat in followup_patterns:
            if re.search(pat, query_lower):
                return True

        # Very short queries in active conversation are typically follow-ups
        if len(query_lower.split()) <= 3:
            return True

        return False

    async def _heuristic_fallback(
        self,
        query: str,
        country: str,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> QueryAnalysisResult:
        """Robust non-LLM heuristic fallback analyzer."""
        query_lower = query.lower().strip()
        words = set(re.findall(r"\b\w+\b", query_lower))

        # Check for financial relevance
        has_fin_keyword = any(k in query_lower for k in self.FINANCIAL_KEYWORDS)
        
        # Check ticker dictionary
        detected_ticker = None
        company_name = None
        common_tickers = getattr(self.market, "COMMON_TICKERS", {})
        for name, ticker in common_tickers.items():
            if name in query_lower:
                detected_ticker = ticker
                company_name = name.title()
                break

        is_financial = has_fin_keyword or bool(detected_ticker)

        # Check if numerical data is requested
        numerical_triggers = {"price", "pe", "ratio", "valuation", "target", "high", "low", "market cap"}
        requires_market_data = bool(detected_ticker) and any(t in query_lower for t in numerical_triggers)

        # Basic sub-queries
        clean_name = company_name or query
        sub_queries = [
            f"{clean_name} latest news developments",
            f"{clean_name} financial performance analysis",
            f"{clean_name} stock overview fundamentals",
        ]

        return QueryAnalysisResult(
            is_financial=is_financial,
            financial_reason="Heuristic evaluation based on financial vocabulary and ticker matching." if is_financial else "Query does not appear related to financial markets or stocks.",
            detected_ticker=detected_ticker,
            company_name=company_name,
            requires_market_data=requires_market_data,
            sub_queries=sub_queries,
            target_date=None,
            reformulated_query=query
        )

    async def analyze(
        self,
        query: str,
        country: str = "IN",
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> QueryAnalysisResult:
        """
        Analyzes user query, validates financial intent, resolves tickers,
        and generates multi-angle sub-queries.
        """
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        history_context = ""
        if chat_history:
            recent_turns = chat_history[-4:]
            history_context = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in recent_turns])

        system_prompt = (
            "You are an expert financial market query analyzer and intent router. "
            "Your job is to analyze user queries for financial intelligence systems, "
            "ensure queries are relevant to business/stocks/economy, identify companies/tickers, "
            "and generate 3 distinct sub-queries for web news search."
        )

        prompt = f"""Analyze this query:
User Query: "{query}"
Today's Date: {today_str}
Target Market: {country} (IN for India, US for USA)
Recent Conversation History (if any):
{history_context or "None"}

Tasks:
1. is_financial: true if the query asks about stocks, companies, business, economy, crypto, or investing; false otherwise.
2. financial_reason: short explanation of classification.
3. company_name: Name of the company mentioned, if any (e.g. "Tata Motors", "Nvidia", "State Bank of India").
4. requires_market_data: true if user is asking for real-time stock price, P/E ratio, market cap, or live quotes.
5. sub_queries: Generate exactly 3 targeted sub-queries for search:
   - Recency query: absolute latest breaking news/events today.
   - Analytical query: expert opinions, market impact, analyst ratings.
   - Factual query: core business details, fundamentals, balance sheet.
6. reformulated_query: If query was a follow-up (e.g. "what about its debt?"), reformulate into a standalone query. If already standalone, keep original.
"""

        try:
            result = await self.llm.generate_structured(
                prompt=prompt,
                response_schema=QueryAnalysisResult,
                system_prompt=system_prompt
            )

            # Resolve ticker symbol via MarketDataClient if company is detected
            if result.company_name or result.detected_ticker:
                search_term = result.detected_ticker or result.company_name
                resolved_ticker = await self.market.resolve_ticker(search_term)
                if resolved_ticker:
                    result.detected_ticker = resolved_ticker

            # If user query is clearly not financial, provide clear reason
            if not result.is_financial:
                result.financial_reason = (
                    result.financial_reason or
                    "Query does not appear related to financial markets, stocks, or economics."
                )

            return result

        except Exception as e:
            logger.warning(f"LLM query analysis failed or API unconfigured ({e}). Utilizing heuristic fallback.")
            fallback = await self._heuristic_fallback(query, country, chat_history)
            if fallback.company_name:
                resolved = await self.market.resolve_ticker(fallback.company_name)
                if resolved:
                    fallback.detected_ticker = resolved
            return fallback
