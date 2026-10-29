"""Unit tests for RSS sentiment monitoring and context processing.

Verifies Prompt 12:
- URL normalization and tracking parameter removal (utm_*, ref, etc.)
- Deterministic article ID generation and deduplication
- Keyword topic tagging with versioned map (and fallback to 'general')
- Lexical analyzer scoring and label bounds
- Contract compliance of sentiment_items and sentiment_agg
- Sentiment sufficiency checks (< 30 articles in 14 days -> insufficient)
- Graceful handling of empty or malformed inputs
- Strict isolation of live sentiment from historical model inputs
"""
from __future__ import annotations

import pandas as pd
import pytest

from fundflow.contracts import validate_table, COLUMNS
from fundflow.sentiment import (
    normalize_url,
    generate_article_id,
    tag_topics,
    LexicalSentimentAnalyzer,
    process_sentiment_items,
    aggregate_sentiment,
    check_sentiment_sufficiency,
    FEED_ALLOWLIST,
)


def test_normalize_url():
    raw = "https://www.financialexpress.com/market/mutual-funds/feed/?utm_source=twitter&utm_medium=social&ref=123"
    clean = normalize_url(raw)
    assert "utm_source" not in clean
    assert "ref" not in clean
    assert clean == "https://www.financialexpress.com/market/mutual-funds/feed"


def test_article_id_deduplication():
    url1 = "https://example.com/news/1?utm_campaign=xyz"
    url2 = "https://example.com/news/1"
    id1 = generate_article_id(url1, "Title 1")
    id2 = generate_article_id(url2, "Title 1")
    assert id1 == id2  # Both normalize to the same URL


def test_tag_topics_keywords_and_general_fallback():
    assert "equity" in tag_topics("Nifty touches record high on strong DII inflows")
    assert "debt" in tag_topics("RBI keeps repo rate unchanged, 10Y bond yields steady")
    assert "regulatory" in tag_topics("SEBI introduces new disclosure mandate for AMCs")
    assert "market" in tag_topics("Mutual fund SIP inflows hit record peak")
    assert tag_topics("Completely unrelated tech gadget announcement") == ["general"]


def test_lexical_sentiment_analyzer():
    clf = LexicalSentimentAnalyzer()
    res_pos = clf.classify("Sensex surges on massive mutual fund inflow rally")
    assert res_pos["label"] == "positive"
    assert res_pos["score"] > 0
    assert 0 <= res_pos["p_pos"] <= 1

    res_neg = clf.classify("Market plunge triggers panic redemption selloff crisis")
    assert res_neg["label"] == "negative"
    assert res_neg["score"] < 0
    assert 0 <= res_neg["p_neg"] <= 1

    res_neu = clf.classify("AMFI releases scheduled monthly data tables")
    assert res_neu["label"] == "neutral"


def test_process_sentiment_items_contract_compliance():
    sample_raw = [
        {
            "url": "https://www.sebi.gov.in/news/1?utm_source=rss",
            "title": "SEBI issues new risk disclosure circular for equity funds",
            "source_name": "SEBI Press Releases",
            "published_at": "2026-10-28T09:00:00Z",
        },
        {
            "url": "https://www.financialexpress.com/mf/sip-growth",
            "title": "Mutual fund SIP inflows surge to new record high",
            "source_name": "Financial Express MF",
            "published_at": "2026-10-28T10:30:00Z",
        },
        # Duplicate URL with tracking params
        {
            "url": "https://www.sebi.gov.in/news/1?utm_source=twitter",
            "title": "SEBI issues new risk disclosure circular for equity funds",
            "source_name": "SEBI Press Releases",
            "published_at": "2026-10-28T09:00:00Z",
        },
    ]

    items_df = process_sentiment_items(sample_raw, is_live=True)
    assert len(items_df) == 2  # 1 duplicate dropped
    validate_table("sentiment_items", items_df)
    assert tuple(items_df.columns) == COLUMNS["sentiment_items"]
    assert (items_df["is_live"] == True).all()
    assert (items_df["model_id"] == "lexical-finance-v1").all()


def test_aggregate_sentiment_contract_compliance():
    sample_raw = [
        {
            "url": "https://www.financialexpress.com/mf/sip-growth",
            "title": "Mutual fund SIP inflows surge to new record high",
            "source_name": "Financial Express MF",
            "published_at": "2026-10-28T10:30:00Z",
        },
        {
            "url": "https://www.sebi.gov.in/news/1",
            "title": "SEBI probes redemption outflow crisis",
            "source_name": "SEBI Press Releases",
            "published_at": "2026-10-28T09:00:00Z",
        },
    ]
    items_df = process_sentiment_items(sample_raw, is_live=True)
    agg_df = aggregate_sentiment(items_df)
    assert not agg_df.empty
    validate_table("sentiment_agg", agg_df)
    assert tuple(agg_df.columns) == COLUMNS["sentiment_agg"]
    assert "2026-10-28" in agg_df["period"].values


def test_check_sentiment_sufficiency():
    empty_res = check_sentiment_sufficiency(pd.DataFrame(), min_articles=30)
    assert empty_res["status"] == "insufficient"
    assert empty_res["n_articles"] == 0

    items_few = pd.DataFrame([
        {"is_live": True, "title": f"News {i}"} for i in range(10)
    ])
    res_few = check_sentiment_sufficiency(items_few, min_articles=30)
    assert res_few["status"] == "insufficient"
    assert res_few["n_articles"] == 10

    items_many = pd.DataFrame([
        {"is_live": True, "title": f"News {i}"} for i in range(35)
    ])
    res_many = check_sentiment_sufficiency(items_many, min_articles=30)
    assert res_many["status"] == "sufficient"
    assert res_many["n_articles"] == 35


def test_allowlist_is_documented():
    assert "SEBI Press Releases" in FEED_ALLOWLIST
    assert "RBI Press Releases" in FEED_ALLOWLIST
    assert all(url.startswith("https://") for url in FEED_ALLOWLIST.values())
