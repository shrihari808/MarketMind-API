"""
Integration Tests for MarketMind API v2 REST Endpoints.
Covers Gateway, Health, Rate Limit Configuration, Chat Sessions, Stocks, Dashboard, and Reddit Sentiment.
"""

import pytest
import httpx
from datetime import datetime, timezone
from app.main import app
from app.api.deps import (
    get_market_client,
    get_dashboard_service,
    get_reddit_rag_service,
)
from app.domain.schemas.market import StockQuote, StockFundamentals, MarketIndex, StockMover
from app.domain.schemas.rag import CommunitySentimentResult


class MockMarketClient:
    """Mock market client returning deterministic quotes and fundamentals."""
    async def get_quote(self, ticker: str):
        if ticker.upper() in ("RELIANCE.NS", "AAPL"):
            return StockQuote(
                ticker=ticker.upper(),
                company_name="Reliance Industries" if "RELIANCE" in ticker else "Apple",
                current_price=2950.0,
                currency="INR" if "NS" in ticker else "USD",
                change=15.0,
                change_percent=0.51,
                market_cap=2000000000000,
                day_high=2970.0,
                day_low=2935.0
            )
        return None

    async def resolve_ticker(self, query: str):
        if query.upper() == "RELIANCE":
            return "RELIANCE.NS"
        return query.upper()

    async def get_fundamentals(self, ticker: str):
        if ticker.upper() in ("RELIANCE.NS", "AAPL"):
            return StockFundamentals(
                ticker=ticker.upper(),
                company_name="Reliance Industries" if "RELIANCE" in ticker else "Apple",
                sector="Energy",
                industry="Oil & Gas",
                market_cap=2000000000000,
                pe_ratio=26.4,
                pb_ratio=2.1,
                roe=0.095,
                debt_to_equity=0.42
            )
        return None


class MockDashboardService:
    """Mock dashboard service returning snapshot data."""
    async def get_snapshot(self, country: str = "IN", force_refresh: bool = False):
        return {
            "country": country,
            "indices": [
                MarketIndex(symbol="^NSEI", name="NIFTY 50", price=25000.0, change=120.0, change_percent=0.48).model_dump()
            ],
            "top_gainers": [
                StockMover(ticker="RELIANCE.NS", name="Reliance Industries", price=2950.0, change_percent=1.2).model_dump()
            ],
            "top_losers": [],
            "market_sentiment": "Bullish momentum in benchmark indices.",
            "prompt_suggestions": [
                {"header": "Reliance Q3", "prompt": "Analyze Reliance Q3 earnings"}
            ],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }


class MockRedditService:
    """Mock reddit service returning structured sentiment."""
    async def analyze_sentiment(self, topic: str, country: str = "IN"):
        return CommunitySentimentResult(
            topic=topic,
            overall_sentiment="Bullish",
            sentiment_score=0.65,
            summary="Strong retail investor sentiment backed by subscriber growth.",
            bullish_arguments=["Strong growth in retail subscribers", "Consistent capital investments"],
            bearish_arguments=["Valuation multiples look stretched"],
            top_discussions=[]
        )


@pytest.fixture
def mock_dependencies():
    """Overrides dependencies with fast, deterministic mock adapters."""
    app.dependency_overrides[get_market_client] = lambda: MockMarketClient()
    app.dependency_overrides[get_dashboard_service] = lambda: MockDashboardService()
    app.dependency_overrides[get_reddit_rag_service] = lambda: MockRedditService()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_root_gateway_json_response():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/", headers={"Accept": "application/json"})
        assert res.status_code == 200
        data = res.json()
        assert data["service"] == "MarketMind Intelligence API"
        assert data["version"] == "2.0.0"
        assert data["status"] == "online"
        assert data["memory_optimized"] is True


@pytest.mark.asyncio
async def test_health_and_rate_limit_inspection_and_update():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        res = await client.get("/api/v2/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"
        assert data["database"] == "healthy"
        assert "rate_limiting" in data

        # 2. Rate limit inspection
        rl_res = await client.get("/api/v2/health/rate-limit")
        assert rl_res.status_code == 200
        rl_data = rl_res.json()
        assert "enabled" in rl_data
        assert "limit_per_minute" in rl_data

        # 3. Dynamic runtime reconfiguration
        conf_res = await client.post(
            "/api/v2/health/rate-limit",
            json={"limit_per_minute": 50, "reset_history": True}
        )
        assert conf_res.status_code == 200
        assert conf_res.json()["limit_per_minute"] == 50


@pytest.mark.asyncio
async def test_chat_sessions_endpoints():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # List sessions
        res = await client.get("/api/v2/chat/sessions", headers={"X-Client-ID": "test_endpoint_client"})
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        # Non-existent session
        bad_get = await client.get("/api/v2/chat/sessions/non_existent_12345", headers={"X-Client-ID": "test_endpoint_client"})
        assert bad_get.status_code == 404

        bad_del = await client.delete("/api/v2/chat/sessions/non_existent_12345", headers={"X-Client-ID": "test_endpoint_client"})
        assert bad_del.status_code == 404


@pytest.mark.asyncio
async def test_stocks_endpoints(mock_dependencies):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Profile (quote + fundamentals)
        res = await client.get("/api/v2/stocks/RELIANCE.NS")
        assert res.status_code == 200
        data = res.json()
        assert data["ticker"] == "RELIANCE.NS"
        assert data["quote"]["current_price"] == 2950.0
        assert data["fundamentals"]["pe_ratio"] == 26.4

        # 2. Quote only
        quote_res = await client.get("/api/v2/stocks/RELIANCE.NS/quote")
        assert quote_res.status_code == 200
        assert quote_res.json()["current_price"] == 2950.0

        # 3. Fundamentals only
        fund_res = await client.get("/api/v2/stocks/RELIANCE.NS/fundamentals")
        assert fund_res.status_code == 200
        assert fund_res.json()["sector"] == "Energy"

        # 4. Unknown stock 404
        bad_stock = await client.get("/api/v2/stocks/UNKNOWN_CO_XYZ/quote")
        assert bad_stock.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_endpoint(mock_dependencies):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v2/dashboard?country=IN")
        assert res.status_code == 200
        data = res.json()
        assert data["country"] == "IN"
        assert len(data["indices"]) == 1
        assert data["indices"][0]["name"] == "NIFTY 50"


@pytest.mark.asyncio
async def test_reddit_sentiment_endpoint(mock_dependencies):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Validation failure: missing or too short topic
        bad_res = await client.post("/api/v2/rag/reddit", json={"topic": " "})
        assert bad_res.status_code == 422

        # 2. Valid topic
        good_res = await client.post("/api/v2/rag/reddit", json={"topic": "Reliance", "country": "IN"})
        assert good_res.status_code == 200
        data = good_res.json()
        assert data["topic"] == "Reliance"
        assert data["overall_sentiment"] == "Bullish"
        assert len(data["bullish_arguments"]) >= 1
