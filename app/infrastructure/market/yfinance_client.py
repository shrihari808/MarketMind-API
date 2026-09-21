"""
Yahoo Finance Financial Market Data Adapter.
Provides zero-cost stock quotes, indices, gainers/losers, and fundamentals via yfinance.
"""

import asyncio
from typing import List, Optional, Dict
import yfinance as yf
from app.core.logging import logger
from app.domain.interfaces.market import MarketDataClient
from app.domain.schemas.market import (
    StockQuote,
    MarketIndex,
    StockMover,
    StockFundamentals,
)


class YFinanceMarketClient(MarketDataClient):
    """Yahoo Finance client executing network calls non-blockingly via asyncio.to_thread."""

    # Common ticker dictionary for rapid Indian & US lookup
    COMMON_TICKERS: Dict[str, str] = {
        "reliance": "RELIANCE.NS",
        "reliance industries": "RELIANCE.NS",
        "tata motors": "TATAMOTORS.NS",
        "tatamotors": "TATAMOTORS.NS",
        "tcs": "TCS.NS",
        "infosys": "INFY.NS",
        "haptik": "INFY.NS",
        "hdfc bank": "HDFCBANK.NS",
        "hdfc": "HDFCBANK.NS",
        "icici bank": "ICICIBANK.NS",
        "sbi": "SBIN.NS",
        "state bank of india": "SBIN.NS",
        "bharti airtel": "BHARTIARTL.NS",
        "itc": "ITC.NS",
        "wipro": "WIPRO.NS",
        "apple": "AAPL",
        "microsoft": "MSFT",
        "google": "GOOGL",
        "alphabet": "GOOGL",
        "amazon": "AMZN",
        "tesla": "TSLA",
        "nvidia": "NVDA",
        "meta": "META",
    }

    # Major indices mapping
    INDICES_MAP = {
        "IN": [
            ("^NSEI", "NIFTY 50"),
            ("^BSESN", "BSE SENSEX"),
            ("^NSEBANK", "NIFTY BANK"),
            ("^CNXIT", "NIFTY IT"),
        ],
        "US": [
            ("^GSPC", "S&P 500"),
            ("^DJI", "Dow Jones"),
            ("^IXIC", "NASDAQ Composite"),
            ("^RUT", "Russell 2000"),
        ],
    }

    async def resolve_ticker(self, company_name: str) -> Optional[str]:
        """Resolves a company name or query into an exchange ticker symbol."""
        cleaned = company_name.strip().lower()
        if cleaned in self.COMMON_TICKERS:
            return self.COMMON_TICKERS[cleaned]

        # If it looks like an explicit ticker already (e.g. AAPL, INFY.NS)
        if company_name.isupper() and (len(company_name) <= 6 or "." in company_name):
            return company_name

        # Attempt search via yfinance Search API in background thread
        def _search():
            try:
                search = yf.Search(company_name, max_results=1)
                quotes = search.quotes
                if quotes and len(quotes) > 0:
                    return quotes[0].get("symbol")
            except Exception:
                pass
            return None

        symbol = await asyncio.to_thread(_search)
        return symbol or f"{company_name.upper().replace(' ', '')}.NS"

    async def get_quote(self, ticker: str) -> Optional[StockQuote]:
        """Fetches latest quote information for a given ticker."""
        def _fetch_quote():
            try:
                t = yf.Ticker(ticker)
                info = t.info
                price = (
                    info.get("currentPrice")
                    or info.get("regularMarketPrice")
                    or info.get("previousClose")
                    or 0.0
                )
                prev = info.get("regularMarketPreviousClose") or price
                change = price - prev
                change_pct = (change / prev * 100) if prev > 0 else 0.0

                return StockQuote(
                    ticker=ticker,
                    company_name=info.get("shortName") or info.get("longName") or ticker,
                    current_price=round(float(price), 2),
                    currency=info.get("currency", "INR"),
                    change=round(float(change), 2),
                    change_percent=round(float(change_pct), 2),
                    market_cap=info.get("marketCap"),
                    pe_ratio=info.get("trailingPE"),
                    day_high=info.get("dayHigh"),
                    day_low=info.get("dayLow"),
                    year_high=info.get("fiftyTwoWeekHigh"),
                    year_low=info.get("fiftyTwoWeekLow"),
                    volume=info.get("regularMarketVolume"),
                )
            except Exception as e:
                logger.error(f"Error fetching quote for {ticker}: {e}")
                return None

        return await asyncio.to_thread(_fetch_quote)

    async def get_quotes_batch(self, tickers: List[str]) -> List[StockQuote]:
        """Fetches quotes for multiple tickers concurrently."""
        tasks = [self.get_quote(t) for t in tickers]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def get_market_indices(self, country: str = "IN") -> List[MarketIndex]:
        """Fetches performance of key market indices."""
        indices = self.INDICES_MAP.get(country.upper(), self.INDICES_MAP["IN"])

        def _fetch_indices():
            result = []
            for symbol, name in indices:
                try:
                    t = yf.Ticker(symbol)
                    info = t.info
                    price = info.get("regularMarketPrice") or info.get("previousClose") or 0.0
                    prev = info.get("regularMarketPreviousClose") or price
                    change = price - prev
                    change_pct = (change / prev * 100) if prev > 0 else 0.0

                    result.append(
                        MarketIndex(
                            symbol=symbol,
                            name=name,
                            price=round(float(price), 2),
                            change=round(float(change), 2),
                            change_percent=round(float(change_pct), 2),
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to fetch index {symbol}: {e}")
            return result

        return await asyncio.to_thread(_fetch_indices)

    async def get_top_movers(self, country: str = "IN") -> Dict[str, List[StockMover]]:
        """Returns top standout gainers and losers from benchmark lists."""
        benchmark_tickers = (
            ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "TATAMOTORS.NS", "ICICIBANK.NS", "ITC.NS", "SBIN.NS"]
            if country.upper() == "IN"
            else ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META"]
        )

        quotes = await self.get_quotes_batch(benchmark_tickers)
        sorted_quotes = sorted(quotes, key=lambda q: q.change_percent, reverse=True)

        gainers = [
            StockMover(
                ticker=q.ticker,
                name=q.company_name,
                price=q.current_price,
                change_percent=q.change_percent,
                summary=f"Up {q.change_percent}% today",
            )
            for q in sorted_quotes if q.change_percent >= 0
        ][:4]

        losers = [
            StockMover(
                ticker=q.ticker,
                name=q.company_name,
                price=q.current_price,
                change_percent=q.change_percent,
                summary=f"Down {abs(q.change_percent)}% today",
            )
            for q in reversed(sorted_quotes) if q.change_percent < 0
        ][:4]

        return {"gainers": gainers, "losers": losers}

    async def get_fundamentals(self, ticker: str) -> Optional[StockFundamentals]:
        """Fetches detailed financial statements and valuation ratios."""
        def _fetch():
            try:
                t = yf.Ticker(ticker)
                info = t.info

                return StockFundamentals(
                    ticker=ticker,
                    company_name=info.get("shortName") or info.get("longName") or ticker,
                    sector=info.get("sector"),
                    industry=info.get("industry"),
                    market_cap=info.get("marketCap"),
                    pe_ratio=info.get("trailingPE"),
                    pb_ratio=info.get("priceToBook"),
                    dividend_yield=info.get("dividendYield"),
                    eps=info.get("trailingEps"),
                    roe=info.get("returnOnEquity"),
                    debt_to_equity=info.get("debtToEquity"),
                    revenue=info.get("totalRevenue"),
                    net_income=info.get("netIncomeToCommon"),
                    free_cash_flow=info.get("freeCashflow"),
                    financials={
                        "gross_margins": info.get("grossMargins"),
                        "operating_margins": info.get("operatingMargins"),
                        "profit_margins": info.get("profitMargins"),
                        "target_mean_price": info.get("targetMeanPrice"),
                        "recommendation_key": info.get("recommendationKey"),
                    },
                )
            except Exception as e:
                logger.error(f"Error fetching fundamentals for {ticker}: {e}")
                return None

        return await asyncio.to_thread(_fetch)
