"""
Unit Tests for Freshness-Aware Reranker, Date Parsing, and Decay Scoring.
"""

from datetime import datetime, timezone, timedelta
import pytest
from app.core.config import get_settings
from app.domain.schemas.rag import SourceCitation, PassageChunk
from app.services.reranker import FreshnessReranker


def test_config_freshness_parameters():
    settings = get_settings()
    assert settings.SEARCH_TIMELIMIT in ("d", "w", "m", "y", None)
    assert settings.MAX_SEARCH_CANDIDATES >= settings.MAX_SCRAPED_SOURCES
    assert settings.MAX_SCRAPED_SOURCES == 5
    assert settings.RAG_HALF_LIFE_DAYS > 0
    assert 0.0 < settings.RAG_RELEVANCE_FLOOR < 1.0


def test_date_parsing_various_formats():
    reranker = FreshnessReranker()

    # ISO 8601
    dt_iso = reranker.parse_date("2026-09-30T15:30:00+00:00")
    assert dt_iso is not None
    assert dt_iso.year == 2026 and dt_iso.month == 9 and dt_iso.day == 30

    # RFC 2822
    dt_rfc = reranker.parse_date("Wed, 30 Sep 2026 15:30:00 +0000")
    assert dt_rfc is not None
    assert dt_rfc.year == 2026 and dt_rfc.month == 9

    # YYYY-MM-DD
    dt_std = reranker.parse_date("2026-08-15")
    assert dt_std is not None
    assert dt_std.year == 2026 and dt_std.month == 8 and dt_std.day == 15

    # Relative formats
    dt_rel_hours = reranker.parse_date("4 hours ago")
    assert dt_rel_hours is not None
    assert abs((datetime.now(timezone.utc) - dt_rel_hours).total_seconds() - 4 * 3600) < 60

    dt_rel_days = reranker.parse_date("3 days ago")
    assert dt_rel_days is not None
    assert abs((datetime.now(timezone.utc) - dt_rel_days).total_seconds() - 3 * 86400) < 60

    # Empty / None
    assert reranker.parse_date(None) is None
    assert reranker.parse_date("") is None


def test_freshness_decay_curve():
    reranker = FreshnessReranker(half_life_days=7.0, relevance_floor=0.25)
    now = datetime.now(timezone.utc)

    # 0 days (now)
    score_now = reranker.calculate_freshness(now.isoformat())
    assert 0.99 <= score_now <= 1.0

    # Exactly 7 days (half-life) -> should be 0.5
    seven_days_ago = now - timedelta(days=7.0)
    score_7d = reranker.calculate_freshness(seven_days_ago.isoformat())
    assert pytest.approx(score_7d, rel=1e-2) == 0.5

    # 14 days -> 1 / (1 + 2) = 0.333
    fourteen_days_ago = now - timedelta(days=14.0)
    score_14d = reranker.calculate_freshness(fourteen_days_ago.isoformat())
    assert pytest.approx(score_14d, rel=1e-2) == 0.333

    # Unknown date -> neutral prior (0.35)
    score_none = reranker.calculate_freshness(None)
    assert score_none == 0.35


def test_pre_filter_citations():
    reranker = FreshnessReranker(half_life_days=7.0)
    now = datetime.now(timezone.utc)

    citations = [
        SourceCitation(
            id=1,
            title="Nvidia Q3 Earnings Surge",
            url="https://reuters.com/1",
            snippet="Nvidia reports record data center revenue and high margin growth",
            publication_date=(now - timedelta(days=1)).isoformat()
        ),
        SourceCitation(
            id=2,
            title="Historical 2021 Nvidia Overview",
            url="https://oldfinance.com/2",
            snippet="Nvidia graphics cards and gaming market analysis",
            publication_date=(now - timedelta(days=500)).isoformat()
        ),
        SourceCitation(
            id=3,
            title="Unrelated Recipe Blog",
            url="https://food.com/3",
            snippet="How to make apple pie and delicious pastries",
            publication_date=now.isoformat()
        ),
        SourceCitation(
            id=4,
            title="Nvidia AI chips analysis",
            url="https://bloomberg.com/4",
            snippet="Nvidia data center chip market demand remains at record high",
            publication_date=(now - timedelta(days=3)).isoformat()
        ),
    ]

    filtered = reranker.pre_filter_citations(query="Nvidia revenue and data center", citations=citations, top_k=2)
    assert len(filtered) == 2
    # The two recent and relevant citations (reuters and bloomberg) should be selected
    urls = [c.url for c in filtered]
    assert "https://reuters.com/1" in urls
    assert "https://bloomberg.com/4" in urls
    assert "https://food.com/3" not in urls


def test_passage_reranking_freshness_bias_and_diversification():
    reranker = FreshnessReranker(half_life_days=7.0, relevance_floor=0.25)
    now = datetime.now(timezone.utc)

    cit_fresh = SourceCitation(
        id=1,
        title="Fresh Source C",
        url="https://source-c.com/news1",
        publication_date=(now - timedelta(days=1)).isoformat()
    )
    cit_old = SourceCitation(
        id=2,
        title="Old Source B",
        url="https://source-b.com/news2",
        publication_date=(now - timedelta(days=120)).isoformat()
    )
    cit_dup_a = SourceCitation(
        id=3,
        title="Duplicate Source A",
        url="https://source-a.com/news3",
        publication_date=now.isoformat()
    )
    cit_dup_a_3 = SourceCitation(
        id=4,
        title="Duplicate Source A 3",
        url="https://source-a.com/news4",
        publication_date=now.isoformat()
    )

    passages = [
        PassageChunk(
            text="Quarterly revenue for the company exceeded consensus estimates with strong operating margins.",
            source=cit_old,
            score=0.0
        ),
        PassageChunk(
            text="Quarterly revenue for the company exceeded consensus estimates with strong operating margins.",
            source=cit_fresh,
            score=0.0
        ),
        PassageChunk(
            text="Quarterly revenue for the company exceeded consensus estimates with strong operating margins.",
            source=cit_dup_a,
            score=0.0
        ),
        PassageChunk(
            text="Quarterly revenue for the company exceeded consensus estimates with strong operating margins.",
            source=cit_dup_a_3,
            score=0.0
        ),
    ]

    reranked = reranker.rerank(
        query="quarterly revenue consensus operating margins",
        passages=passages,
        top_k=3,
        max_per_domain=2
    )

    # 1. Fresh source from source-c should score higher than identical old source from source-b
    scores = {p.source.url: p.score for p in reranked}
    assert scores["https://source-c.com/news1"] > scores.get("https://source-b.com/news2", 0.0)

    # 2. Domain diversification: source-a should appear at most 2 times
    source_a_count = sum(1 for p in reranked if "source-a.com" in p.source.url)
    assert source_a_count <= 2
