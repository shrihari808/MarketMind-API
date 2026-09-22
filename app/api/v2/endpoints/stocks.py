"""
Real-Time Stock Quotes and Fundamental Intelligence Endpoints.
Supports Indian (.NS, .BO) and US ticker exchanges via YFinanceMarketClient.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_market_client
from app.domain.interfaces.market import MarketDataClient
from app.domain.schemas.market import StockQuote, StockFundamentals

router = APIRouter(prefix="/stocks", tags=["Stocks & Fundamentals"])


@router.get(
    "/{ticker}",
    summary="Consolidated Real-Time Quote and Fundamentals for a Ticker"
)
async def get_stock_profile(
    ticker: str,
    market_client: MarketDataClient = Depends(get_market_client)
) -> Dict[str, Any]:
    """
    Returns consolidated financial intelligence for a ticker: live price, day high/low,
    52-week range, market cap, P/E, EPS, ROE, debt-to-equity, and profit margins.
    """
    clean_ticker = ticker.upper().strip()
    quote = await market_client.get_quote(clean_ticker)
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock data not found for ticker '{clean_ticker}'."
        )

    fundamentals = await market_client.get_fundamentals(clean_ticker)

    return {
        "ticker": clean_ticker,
        "quote": quote,
        "fundamentals": fundamentals
    }


@router.get(
    "/{ticker}/quote",
    response_model=StockQuote,
    summary="Live Real-Time Stock Quote"
)
async def get_stock_quote(
    ticker: str,
    market_client: MarketDataClient = Depends(get_market_client)
) -> StockQuote:
    """
    Retrieves real-time price, day high/low, currency, and percent change.
    """
    clean_ticker = ticker.upper().strip()
    quote = await market_client.get_quote(clean_ticker)
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quote not found for ticker '{clean_ticker}'."
        )
    return quote


@router.get(
    "/{ticker}/fundamentals",
    response_model=StockFundamentals,
    summary="Financial Fundamentals & Valuation Ratios"
)
async def get_stock_fundamentals(
    ticker: str,
    market_client: MarketDataClient = Depends(get_market_client)
) -> StockFundamentals:
    """
    Retrieves institutional fundamental metrics (P/E, P/B, ROE, Debt/Equity, Free Cash Flow, Revenue).
    """
    clean_ticker = ticker.upper().strip()
    fundamentals = await market_client.get_fundamentals(clean_ticker)
    if not fundamentals:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fundamentals not found for ticker '{clean_ticker}'."
        )
    return fundamentals
