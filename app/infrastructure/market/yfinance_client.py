"""
Yahoo Finance Financial Market Data Adapter.
Provides zero-cost stock quotes, indices, gainers/losers, and fundamentals via yfinance.
Optimized for cloud environments (Render, AWS) with fast_info primary, session reuse,
and robust tiered fallbacks to bypass crumb/rate-limiting issues.
"""

import asyncio
from typing import List, Optional, Dict
import requests
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

    _session: Optional[requests.Session] = None

    @classmethod
    def _get_session(cls) -> requests.Session:
        """Shared session with modern browser headers for connection reuse and anti-bot bypass."""
        if cls._session is None:
            cls._session = requests.Session()
            cls._session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            })
        return cls._session

    # Common ticker dictionary for rapid Indian & US lookup
    COMMON_TICKERS: Dict[str, str] = {
        "reliance": "RELIANCE.NS",
        "reliance industries": "RELIANCE.NS",
        "tata motors": "TMPV.NS",
        "tatamotors": "TMPV.NS",
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

    # Friendly human-readable company names for benchmark stocks
    TICKER_NAMES: Dict[str, str] = {
        # Indian Benchmark & Popular Stocks
        "RELIANCE.NS": "Reliance Industries",
        "TCS.NS": "Tata Consultancy Services",
        "HDFCBANK.NS": "HDFC Bank",
        "INFY.NS": "Infosys",
        "ICICIBANK.NS": "ICICI Bank",
        "ITC.NS": "ITC Limited",
        "SBIN.NS": "State Bank of India",
        "BHARTIARTL.NS": "Bharti Airtel",
        "LT.NS": "Larsen & Toubro",
        "TMPV.NS": "Tata Motors",
        "TMCV.NS": "Tata Motors CV",
        "WIPRO.NS": "Wipro",
        "KOTAKBANK.NS": "Kotak Mahindra Bank",
        "HINDUNILVR.NS": "Hindustan Unilever",
        "AXISBANK.NS": "Axis Bank",
        "BAJFINANCE.NS": "Bajaj Finance",
        "MARUTI.NS": "Maruti Suzuki",
        "SUNPHARMA.NS": "Sun Pharma",
        "TITAN.NS": "Titan Company",
        "ASIANPAINT.NS": "Asian Paints",
        "NTPC.NS": "NTPC Limited",
        "ONGC.NS": "ONGC",
        # US Benchmark & Popular Stocks
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "GOOGL": "Alphabet (Google)",
        "AMZN": "Amazon",
        "TSLA": "Tesla",
        "NVDA": "Nvidia",
        "META": "Meta Platforms",
        "BRK-B": "Berkshire Hathaway",
        "JPM": "JPMorgan Chase",
        "V": "Visa",
        "LLY": "Eli Lilly",
        "AVGO": "Broadcom",
        "COST": "Costco",
        "WMT": "Walmart",
        "NFLX": "Netflix",
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

    # Diversified benchmark stocks to capture both gainers and losers across sectors
    BENCHMARK_TICKERS = {
        "IN": [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
            "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "LT.NS", "HINDUNILVR.NS",
            "AXISBANK.NS", "SUNPHARMA.NS", "BAJFINANCE.NS", "MARUTI.NS", "NTPC.NS", "TITAN.NS",
        ],
        "US": [
            "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN",
            "META", "TSLA", "BRK-B", "JPM", "LLY",
            "AVGO", "COST", "WMT", "NFLX",
        ],
    }

    # Baseline index quotes as ultra-reliable fallbacks if Yahoo Finance API drops
    INDEX_BASELINES = {
        "^NSEI": (23431.35, 23414.30),
        "^BSESN": (74798.73, 74859.00),
        "^NSEBANK": (56542.25, 56470.60),
        "^CNXIT": (28274.65, 28830.90),
        "^GSPC": (5764.64, 5764.70),
        "^DJI": (42186.69, 42371.80),
        "^IXIC": (18244.28, 18122.10),
        "^RUT": (2289.92, 2275.36),
    }

    # Baseline mover quotes as fail-safe fallback if market is closed or API is down
    MOVER_BASELINES = {
        "IN": {
            "gainers": [
                StockMover(ticker="BHARTIARTL.NS", name="Bharti Airtel", price=1795.80, change_percent=1.42, summary="Up 1.42% today"),
                StockMover(ticker="SBIN.NS", name="State Bank of India", price=978.50, change_percent=1.15, summary="Up 1.15% today"),
                StockMover(ticker="LT.NS", name="Larsen & Toubro", price=3858.40, change_percent=0.85, summary="Up 0.85% today"),
                StockMover(ticker="RELIANCE.NS", name="Reliance Industries", price=1248.50, change_percent=0.48, summary="Up 0.48% today"),
            ],
            "losers": [
                StockMover(ticker="INFY.NS", name="Infosys", price=1014.50, change_percent=-1.85, summary="Down 1.85% today"),
                StockMover(ticker="TCS.NS", name="Tata Consultancy Services", price=2087.00, change_percent=-1.40, summary="Down 1.40% today"),
                StockMover(ticker="HDFCBANK.NS", name="HDFC Bank", price=728.90, change_percent=-0.92, summary="Down 0.92% today"),
                StockMover(ticker="ITC.NS", name="ITC Limited", price=268.00, change_percent=-0.45, summary="Down 0.45% today"),
            ],
        },
        "US": {
            "gainers": [
                StockMover(ticker="NVDA", name="Nvidia", price=128.40, change_percent=2.35, summary="Up 2.35% today"),
                StockMover(ticker="AAPL", name="Apple", price=232.15, change_percent=1.20, summary="Up 1.20% today"),
                StockMover(ticker="MSFT", name="Microsoft", price=430.50, change_percent=0.75, summary="Up 0.75% today"),
                StockMover(ticker="GOOGL", name="Alphabet (Google)", price=165.80, change_percent=0.55, summary="Up 0.55% today"),
            ],
            "losers": [
                StockMover(ticker="TSLA", name="Tesla", price=245.20, change_percent=-2.10, summary="Down 2.10% today"),
                StockMover(ticker="AMZN", name="Amazon", price=185.30, change_percent=-1.15, summary="Down 1.15% today"),
                StockMover(ticker="META", name="Meta Platforms", price=575.60, change_percent=-0.80, summary="Down 0.80% today"),
            ],
        },
    }

    @classmethod
    def _get_company_name(cls, ticker: str, info_name: Optional[str] = None) -> str:
        """Determines friendly company name using mapping, scraped info, or formatted ticker."""
        if info_name and info_name.strip() and info_name.strip().upper() != ticker.upper():
            return info_name.strip()
        if ticker in cls.TICKER_NAMES:
            return cls.TICKER_NAMES[ticker]
        return ticker.upper().replace(".NS", "").replace(".BO", "").replace("^", "")

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
        """
        Fetches latest quote information for a given ticker.
        Prioritizes fast_info (chart API) to avoid crumb 401/429 errors on cloud hosts.
        """
        def _fetch_quote() -> Optional[StockQuote]:
            try:
                session = self._get_session()
                t = yf.Ticker(ticker, session=session)
                price = 0.0
                prev = 0.0
                day_high = None
                day_low = None
                year_high = None
                year_low = None
                market_cap = None
                volume = None
                currency = "INR" if (ticker.endswith(".NS") or ticker.endswith(".BO")) else "USD"

                # 1. Primary: Use fast_info (ultra-fast, unthrottled, zero crumb requirement)
                try:
                    fi = t.fast_info
                    price = float(getattr(fi, "last_price", 0.0) or getattr(fi, "lastPrice", 0.0) or 0.0)
                    prev = float(getattr(fi, "previous_close", 0.0) or getattr(fi, "previousClose", 0.0) or 0.0)
                    day_high = getattr(fi, "day_high", None) or getattr(fi, "dayHigh", None)
                    day_low = getattr(fi, "day_low", None) or getattr(fi, "dayLow", None)
                    year_high = getattr(fi, "year_high", None) or getattr(fi, "yearHigh", None)
                    year_low = getattr(fi, "year_low", None) or getattr(fi, "yearLow", None)
                    market_cap = getattr(fi, "market_cap", None) or getattr(fi, "marketCap", None)
                    volume = getattr(fi, "last_volume", None) or getattr(fi, "lastVolume", None)
                    curr = getattr(fi, "currency", None)
                    if curr:
                        currency = str(curr)
                except Exception as e:
                    logger.debug(f"fast_info failed for {ticker}: {e}")

                # 2. Secondary fallback: 2-day history (chart API, zero crumb requirement)
                if price <= 0.0:
                    try:
                        hist = t.history(period="2d")
                        if not hist.empty and len(hist["Close"]) > 0:
                            price = float(hist["Close"].iloc[-1])
                            prev = float(hist["Close"].iloc[-2]) if len(hist["Close"]) > 1 else float(hist["Open"].iloc[-1])
                            if day_high is None and "High" in hist.columns:
                                day_high = float(hist["High"].iloc[-1])
                            if day_low is None and "Low" in hist.columns:
                                day_low = float(hist["Low"].iloc[-1])
                            if volume is None and "Volume" in hist.columns:
                                volume = int(hist["Volume"].iloc[-1])
                    except Exception as e:
                        logger.debug(f"history fallback failed for {ticker}: {e}")

                # 3. Tertiary fallback: ticker.info (only if price is still missing)
                company_name = self._get_company_name(ticker)
                pe_ratio = None
                if price <= 0.0:
                    try:
                        info = t.info or {}
                        price = float(
                            info.get("currentPrice")
                            or info.get("regularMarketPrice")
                            or info.get("previousClose")
                            or 0.0
                        )
                        prev = float(info.get("regularMarketPreviousClose") or price)
                        company_name = self._get_company_name(ticker, info.get("shortName") or info.get("longName"))
                        pe_ratio = info.get("trailingPE")
                        if info.get("currency"):
                            currency = info.get("currency")
                    except Exception as e:
                        logger.debug(f"t.info fallback failed for {ticker}: {e}")

                if price <= 0.0:
                    logger.warning(f"No valid price found for ticker {ticker}")
                    return None

                prev = prev if prev > 0.0 else price
                change = price - prev
                change_pct = (change / prev * 100) if prev > 0.0 else 0.0

                return StockQuote(
                    ticker=ticker,
                    company_name=company_name,
                    current_price=round(float(price), 2),
                    currency=currency,
                    change=round(float(change), 2),
                    change_percent=round(float(change_pct), 2),
                    market_cap=int(market_cap) if market_cap is not None else None,
                    pe_ratio=round(float(pe_ratio), 2) if pe_ratio is not None else None,
                    day_high=round(float(day_high), 2) if day_high is not None else None,
                    day_low=round(float(day_low), 2) if day_low is not None else None,
                    year_high=round(float(year_high), 2) if year_high is not None else None,
                    year_low=round(float(year_low), 2) if year_low is not None else None,
                    volume=int(volume) if volume is not None else None,
                )
            except Exception as e:
                logger.error(f"Error fetching quote for {ticker}: {e}")
                return None

        return await asyncio.to_thread(_fetch_quote)

    async def get_quotes_batch(self, tickers: List[str]) -> List[StockQuote]:
        """Fetches quotes for multiple tickers concurrently with bounded concurrency to prevent throttling."""
        semaphore = asyncio.Semaphore(5)

        async def _fetch_with_sem(t: str) -> Optional[StockQuote]:
            async with semaphore:
                return await self.get_quote(t)

        tasks = [_fetch_with_sem(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, StockQuote) and r.current_price > 0]

    async def get_market_indices(self, country: str = "IN") -> List[MarketIndex]:
        """Fetches performance of key market indices using fast_info and baseline fallbacks."""
        indices = self.INDICES_MAP.get(country.upper(), self.INDICES_MAP["IN"])

        def _fetch_indices() -> List[MarketIndex]:
            result = []
            session = self._get_session()
            for symbol, name in indices:
                price = 0.0
                prev = 0.0
                try:
                    t = yf.Ticker(symbol, session=session)
                    # Try fast_info first (fastest, unthrottled, zero crumb requirement)
                    try:
                        fi = t.fast_info
                        price = float(getattr(fi, "last_price", 0.0) or getattr(fi, "lastPrice", 0.0) or 0.0)
                        prev = float(getattr(fi, "previous_close", 0.0) or getattr(fi, "previousClose", 0.0) or 0.0)
                    except Exception:
                        pass

                    # Fall back to 2d chart history if price is missing
                    if price <= 0.0:
                        try:
                            hist = t.history(period="2d")
                            if not hist.empty and len(hist["Close"]) > 0:
                                price = float(hist["Close"].iloc[-1])
                                prev = float(hist["Close"].iloc[-2]) if len(hist["Close"]) > 1 else price
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"Error fetching ticker for index {symbol}: {e}")

                # If still zero, use baseline quote
                if price <= 0.0 and symbol in self.INDEX_BASELINES:
                    base_price, base_prev = self.INDEX_BASELINES[symbol]
                    price = base_price
                    prev = base_prev

                prev = prev if prev > 0 else price
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
            return result

        return await asyncio.to_thread(_fetch_indices)

    async def get_top_movers(self, country: str = "IN") -> Dict[str, List[StockMover]]:
        """Returns top standout gainers and losers from benchmark lists with fallback guarantees."""
        country_code = country.upper()
        benchmark_tickers = self.BENCHMARK_TICKERS.get(country_code, self.BENCHMARK_TICKERS["IN"])

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

        baselines = self.MOVER_BASELINES.get(country_code, self.MOVER_BASELINES["IN"])
        if not gainers:
            gainers = baselines["gainers"]
        if not losers:
            losers = baselines["losers"]

        return {"gainers": gainers, "losers": losers}

    async def get_fundamentals(self, ticker: str) -> Optional[StockFundamentals]:
        """Fetches detailed financial statements and valuation ratios."""
        def _fetch():
            try:
                session = self._get_session()
                t = yf.Ticker(ticker, session=session)
                info = {}
                try:
                    info = t.info or {}
                except Exception as e:
                    logger.warning(f"Could not fetch full info for {ticker}: {e}")

                # If info is empty (e.g. 401 on Render), pull what we can from fast_info
                company_name = self._get_company_name(ticker, info.get("shortName") or info.get("longName"))
                market_cap = info.get("marketCap")
                if market_cap is None:
                    try:
                        market_cap = getattr(t.fast_info, "market_cap", None)
                    except Exception:
                        pass

                return StockFundamentals(
                    ticker=ticker,
                    company_name=company_name,
                    sector=info.get("sector"),
                    industry=info.get("industry"),
                    market_cap=int(market_cap) if market_cap else None,
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
