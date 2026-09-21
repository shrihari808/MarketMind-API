"""
Pydantic Schemas for Financial Market Data and Dashboards.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class StockQuote(BaseModel):
    """Real-time or delayed stock quote."""
    ticker: str
    company_name: str
    current_price: float
    currency: str = "INR"
    change: float = 0.0
    change_percent: float = 0.0
    market_cap: Optional[int] = None
    pe_ratio: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    year_high: Optional[float] = None
    year_low: Optional[float] = None
    volume: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MarketIndex(BaseModel):
    """Broad market index performance (e.g. Nifty 50, S&P 500)."""
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float


class StockMover(BaseModel):
    """Top gainer or loser stock entry."""
    ticker: str
    name: str
    price: float
    change_percent: float
    summary: Optional[str] = None


class MarketDashboardSnapshot(BaseModel):
    """Aggregated market dashboard snapshot."""
    country: str = "IN"
    indices: List[MarketIndex] = []
    top_gainers: List[StockMover] = []
    top_losers: List[StockMover] = []
    market_sentiment: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StockFundamentals(BaseModel):
    """Comprehensive fundamental metrics for equity research."""
    ticker: str
    company_name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[int] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    eps: Optional[float] = None
    roe: Optional[float] = None
    debt_to_equity: Optional[float] = None
    revenue: Optional[int] = None
    net_income: Optional[int] = None
    free_cash_flow: Optional[int] = None
    financials: Dict[str, Any] = Field(default_factory=dict)
