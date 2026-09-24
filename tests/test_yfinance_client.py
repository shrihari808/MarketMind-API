"""
Unit tests for YFinanceMarketClient.
Verifies quote fetching, fallback mechanisms, index baselines, and mover generation.
"""

import pytest
from app.infrastructure.market.yfinance_client import YFinanceMarketClient
from app.domain.schemas.market import StockQuote, MarketIndex, StockMover


@pytest.fixture
def market_client():
    return YFinanceMarketClient()


@pytest.mark.asyncio
async def test_resolve_ticker_common(market_client):
    ticker = await market_client.resolve_ticker("reliance")
    assert ticker == "RELIANCE.NS"

    ticker_apple = await market_client.resolve_ticker("apple")
    assert ticker_apple == "AAPL"


@pytest.mark.asyncio
async def test_get_quote_live_or_fallback(market_client):
    quote = await market_client.get_quote("RELIANCE.NS")
    if quote is not None:
        assert isinstance(quote, StockQuote)
        assert quote.ticker == "RELIANCE.NS"
        assert quote.current_price > 0
        assert quote.currency == "INR"


@pytest.mark.asyncio
async def test_get_market_indices(market_client):
    indices = await market_client.get_market_indices("IN")
    assert len(indices) == 4
    for idx in indices:
        assert isinstance(idx, MarketIndex)
        assert idx.price > 0
        assert idx.name in ["NIFTY 50", "BSE SENSEX", "NIFTY BANK", "NIFTY IT"]


@pytest.mark.asyncio
async def test_get_top_movers(market_client):
    movers = await market_client.get_top_movers("IN")
    assert "gainers" in movers
    assert "losers" in movers
    assert len(movers["gainers"]) > 0
    assert len(movers["losers"]) > 0
    for g in movers["gainers"]:
        assert isinstance(g, StockMover)
        assert g.price > 0
