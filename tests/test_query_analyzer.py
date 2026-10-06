"""
Unit Tests for Financial Query Analyzer & Intent Classifier.
Tests follow-up detection, financial keyword recognition, ticker resolution, and LLM synthesis.
"""

import pytest
from app.domain.schemas.rag import QueryAnalysisResult
from app.services.query_analyzer import QueryAnalyzer
from app.infrastructure.market.yfinance_client import YFinanceMarketClient


class MockLLMAnalyzer:
    """Mock LLM returning structured query analysis."""
    async def generate_structured(self, prompt, response_schema, system_prompt=None):
        return QueryAnalysisResult(
            is_financial=True,
            financial_reason="Query asks for equity valuation metrics.",
            detected_ticker="INFY.NS",
            company_name="Infosys",
            requires_market_data=True,
            sub_queries=[
                "Infosys Q3 revenue and operating margin",
                "Infosys latest attrition and deal pipeline",
                "Infosys valuation multiples"
            ],
            target_date="2026-10-01",
            reformulated_query="Infosys stock fundamentals and earnings"
        )


def test_followup_question_detection():
    analyzer = QueryAnalyzer()

    # 1. Pronoun patterns in multi-turn conversation
    history = [{"role": "user", "content": "Tell me about Tata Motors"}]
    assert analyzer._is_followup_question("What is its P/E ratio?", history) is True
    assert analyzer._is_followup_question("How about their EV margins?", history) is True
    assert analyzer._is_followup_question("Compare this to Mahindra", history) is True

    # 2. Short queries in conversation
    assert analyzer._is_followup_question("and dividend?", history) is True
    assert analyzer._is_followup_question("why?", history) is True

    # 3. Independent first-turn queries
    assert analyzer._is_followup_question("What is the current price of Reliance?", None) is False
    assert analyzer._is_followup_question("What is the current price of Reliance?", []) is False


@pytest.mark.asyncio
async def test_heuristic_financial_keyword_matching():
    analyzer = QueryAnalyzer()

    # Positive financial queries
    res_bond = await analyzer._heuristic_fallback("What is the current 10-year treasury yield?", "US")
    assert res_bond.is_financial is True

    res_ebitda = await analyzer._heuristic_fallback("Explain EBITDA and operating cash flow", "IN")
    assert res_ebitda.is_financial is True

    res_split = await analyzer._heuristic_fallback("Did the company announce a stock split or bonus share?", "IN")
    assert res_split.is_financial is True

    # Negative non-financial queries
    res_cake = await analyzer._heuristic_fallback("How do I bake a chocolate cake at home?", "IN")
    assert res_cake.is_financial is False

    res_capital = await analyzer._heuristic_fallback("What is the capital city of Australia?", "IN")
    assert res_capital.is_financial is False


@pytest.mark.asyncio
async def test_heuristic_ticker_and_company_detection():
    analyzer = QueryAnalyzer()

    # Indian stock matching
    res_rel = await analyzer._heuristic_fallback("Is Reliance a good stock for long term?", "IN")
    assert res_rel.is_financial is True
    assert res_rel.detected_ticker == "RELIANCE.NS"
    assert res_rel.company_name == "Reliance"

    res_tcs = await analyzer._heuristic_fallback("TCS revenue performance", "IN")
    assert res_tcs.is_financial is True
    assert res_tcs.detected_ticker == "TCS.NS"

    # US stock matching
    res_nvda = await analyzer._heuristic_fallback("Nvidia Blackwell GPU shipments", "US")
    assert res_nvda.is_financial is True
    assert res_nvda.detected_ticker == "NVDA"

    res_aapl = await analyzer._heuristic_fallback("Apple quarterly services growth", "US")
    assert res_aapl.is_financial is True
    assert res_aapl.detected_ticker == "AAPL"


@pytest.mark.asyncio
async def test_heuristic_market_data_required_flag():
    analyzer = QueryAnalyzer()

    # Query with numbers/price keywords
    res_price = await analyzer._heuristic_fallback("What is Reliance stock price and target valuation?", "IN")
    assert res_price.requires_market_data is True

    # Query without numerical keywords
    res_history = await analyzer._heuristic_fallback("Tell me about Reliance corporate history and subsidiaries", "IN")
    assert res_history.requires_market_data is False


@pytest.mark.asyncio
async def test_analyze_with_llm():
    mock_llm = MockLLMAnalyzer()
    analyzer = QueryAnalyzer(llm_client=mock_llm)

    result = await analyzer.analyze("Tell me about Infosys")
    assert result.is_financial is True
    assert result.detected_ticker == "INFY.NS"
    assert result.company_name == "Infosys"
    assert len(result.sub_queries) == 3
    assert result.requires_market_data is True
