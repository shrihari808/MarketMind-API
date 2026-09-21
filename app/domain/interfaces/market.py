"""
Financial Market Data Client Interface.
Defines the contract for fetching quotes, market indices, top movers, and company fundamentals.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from app.domain.schemas.market import (
    StockQuote,
    MarketIndex,
    StockMover,
    StockFundamentals,
)


class MarketDataClient(ABC):
    """Abstract Base Class for financial market data providers."""

    @abstractmethod
    async def get_quote(self, ticker: str) -> Optional[StockQuote]:
        """Fetches latest quote for a stock ticker."""
        pass

    @abstractmethod
    async def get_quotes_batch(self, tickers: List[str]) -> List[StockQuote]:
        """Fetches quotes for multiple tickers in parallel."""
        pass

    @abstractmethod
    async def get_market_indices(self, country: str = "IN") -> List[MarketIndex]:
        """Fetches major market indices for a country (e.g. NIFTY 50, S&P 500)."""
        pass

    @abstractmethod
    async def get_top_movers(self, country: str = "IN") -> Dict[str, List[StockMover]]:
        """Returns standout gainers and losers."""
        pass

    @abstractmethod
    async def get_fundamentals(self, ticker: str) -> Optional[StockFundamentals]:
        """Retrieves financial ratios, statements, and overview."""
        pass

    @abstractmethod
    async def resolve_ticker(self, company_name: str) -> Optional[str]:
        """Resolves a company name or loose identifier into an exchange ticker symbol."""
        pass
