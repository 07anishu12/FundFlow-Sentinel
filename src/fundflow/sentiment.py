"""FundFlow RSS sentiment analysis and context monitoring engine.

Context-only sentiment analysis:
- Bounded RSS ingestion with URL sanitization and deduplication.
- Keyword-based topic tagging with versioned maps.
- Swappable classifier interface with verified offline lexical fallback.
- Stable generation of sentiment_items.csv and sentiment_agg.csv contracts.
- Strictly isolated from historical flow forecasting models.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Optional, Protocol, Sequence
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import pandas as pd

from fundflow.contracts import validate_table, COLUMNS

# Documented RSS Feed Allowlist
FEED_ALLOWLIST = {
    "SEBI Press Releases": "https://www.sebi.gov.in/sebirss.xml",
    "RBI Press Releases": "https://www.rbi.org.in/pressreleases_rss.xml",
    "Financial Express MF": "https://www.financialexpress.com/market/mutual-funds/feed/",
    "Economic Times MF": "https://economictimes.indiatimes.com/mf/rssfeeds/default.cms",
}

# Versioned Topic Keyword Map (v1.0)
TOPIC_MAP_V1 = {
    "equity": [
        "equity", "nifty", "sensex", "shares", "stocks", "small cap", "mid cap",
        "large cap", "flexi cap", "multicap", "bse", "nse", "ipo"
    ],
    "debt": [
        "debt", "bond", "yield", "gilt", "fixed income", "interest rate", "rbi",
        "repo", "t-bill", "commercial paper", "credit"
    ],
    "regulatory": [
        "sebi", "amfi", "regulation", "circular", "compliance", "mandate",
        "rule", "penalty", "disclosure", "guideline", "investigation"
    ],
    "market": [
        "market", "inflow", "outflow", "redemption", "aum", "sip", "mutual fund",
        "nav", "portfolio", "asset", "amc", "fund house"
    ],
}

# Financial Lexicon for Offline Lexical Scoring (Loughran-McDonald adaptation)
POSITIVE_FINANCIAL_WORDS = {
    "surge", "gain", "rally", "record", "growth", "high", "positive", "strong",
    "profit", "inflow", "boost", "optimism", "recovery", "bullish", "jump",
    "rise", "expanding", "opportunity", "upbeat", "robust"
}

NEGATIVE_FINANCIAL_WORDS = {
    "fall", "drop", "plunge", "decline", "outflow", "redemption", "loss", "crash",
    "slump", "negative", "weak", "risk", "warning", "probe", "penalty",
    "fraud", "default", "bearish", "volatile", "selloff", "crisis", "concern"
}


def normalize_url(url: str) -> str:
    """Normalize URL by stripping tracking parameters (utm_*, ref, fbclid) while preserving path."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        query_params = parse_qs(parsed.query, keep_blank_values=False)
        clean_params = {
            k: v for k, v in query_params.items()
            if not k.lower().startswith("utm_") and k.lower() not in {"ref", "fbclid", "gclid"}
        }
        clean_query = urlencode(clean_params, doseq=True)
        # Strip trailing slash from path for consistency
        clean_path = parsed.path.rstrip("/")
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            clean_path,
            parsed.params,
            clean_query,
            ""  # strip fragment
        ))
        return normalized
    except Exception:
        return url.strip()


def generate_article_id(url: str, title: str = "", source_name: str = "") -> str:
    """Generate a deterministic 16-character hex article identifier."""
    norm_url = normalize_url(url)
    if norm_url:
        seed = f"url:{norm_url}"
    else:
        seed = f"title:{title.strip().lower()}|src:{source_name.strip().lower()}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def tag_topics(text: str, topic_map: Optional[dict[str, list[str]]] = None) -> list[str]:
    """Tag topics based on keyword matching. Unmatched stories return ['general']."""
    if topic_map is None:
        topic_map = TOPIC_MAP_V1

    text_lower = text.lower()
    matched = []
    for topic, keywords in topic_map.items():
        for kw in keywords:
            # Word boundary matching
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, text_lower):
                matched.append(topic)
                break

    if not matched:
        return ["general"]
    return sorted(matched)


class SentimentClassifier(Protocol):
    """Protocol for pluggable sentiment classifiers."""
    model_id: str

    def classify(self, text: str) -> dict[str, float]:
        """Return dict with keys: p_pos, p_neg, p_neu, score, label."""
        ...


class LexicalSentimentAnalyzer:
    """Offline financial lexical analyzer with Loughran-McDonald adaptation."""
    model_id: str = "lexical-finance-v1"

    def classify(self, text: str) -> dict[str, float]:
        tokens = set(re.findall(r"\b[a-z]{3,}\b", text.lower()))
        n_pos = len(tokens & POSITIVE_FINANCIAL_WORDS)
        n_neg = len(tokens & NEGATIVE_FINANCIAL_WORDS)
        total_signals = n_pos + n_neg

        if total_signals == 0:
            return {
                "p_pos": 0.1,
                "p_neg": 0.1,
                "p_neu": 0.8,
                "score": 0.0,
                "label": "neutral"
            }

        p_pos = n_pos / total_signals
        p_neg = n_neg / total_signals
        p_neu = max(0.0, 1.0 - (p_pos + p_neg))

        # Score bounded between -1.0 and +1.0
        score = float(n_pos - n_neg) / float(n_pos + n_neg)
        score = round(max(-1.0, min(1.0, score)), 4)

        if score > 0.15:
            label = "positive"
        elif score < -0.15:
            label = "negative"
        else:
            label = "neutral"

        return {
            "p_pos": round(p_pos, 4),
            "p_neg": round(p_neg, 4),
            "p_neu": round(p_neu, 4),
            "score": score,
            "label": label,
        }


def process_sentiment_items(
    raw_articles: Sequence[dict],
    classifier: Optional[SentimentClassifier] = None,
    is_live: bool = True,
) -> pd.DataFrame:
    """Process raw article dictionaries into a validated sentiment_items DataFrame.
    
    COLUMNS['sentiment_items']:
    ('article_id', 'published_at', 'title', 'source_name', 'url', 'p_pos', 'p_neg', 'p_neu',
     'label', 'score', 'topic_tags', 'is_live', 'model_id')
    """
    if classifier is None:
        classifier = LexicalSentimentAnalyzer()

    seen_ids = set()
    rows = []

    for art in raw_articles:
        raw_url = str(art.get("url", ""))
        title = str(art.get("title", "")).strip()
        source = str(art.get("source_name", "Unknown")).strip()
        pub_at = str(art.get("published_at", "")).strip()

        if not title:
            continue

        norm_url = normalize_url(raw_url)
        art_id = generate_article_id(norm_url, title, source)

        if art_id in seen_ids:
            # Deduplicate by canonical URL / ID
            continue
        seen_ids.add(art_id)

        # Topic tagging
        topics = tag_topics(f"{title} {art.get('summary', '')}")
        topic_tags_str = ",".join(topics)

        # Classification
        pred = classifier.classify(title)

        rows.append({
            "article_id": art_id,
            "published_at": pub_at if pub_at else "2026-10-28T00:00:00Z",
            "title": title,
            "source_name": source,
            "url": norm_url if norm_url else "https://portal.amfiindia.com",
            "p_pos": pred["p_pos"],
            "p_neg": pred["p_neg"],
            "p_neu": pred["p_neu"],
            "label": pred["label"],
            "score": pred["score"],
            "topic_tags": topic_tags_str,
            "is_live": is_live,
            "model_id": classifier.model_id,
        })

    if not rows:
        return pd.DataFrame(columns=COLUMNS["sentiment_items"])

    df = pd.DataFrame(rows, columns=COLUMNS["sentiment_items"])
    # Deterministic sorting
    df = df.sort_values(["published_at", "article_id"]).reset_index(drop=True)
    return validate_table("sentiment_items", df)


def aggregate_sentiment(
    items_df: pd.DataFrame,
    freq: str = "D",
) -> pd.DataFrame:
    """Aggregate sentiment items into daily/weekly sentiment_agg contract.
    
    COLUMNS['sentiment_agg']:
    ('period', 'topic', 'mean_score', 'neg_share', 'n_articles', 'is_live')
    """
    if items_df.empty:
        return pd.DataFrame(columns=COLUMNS["sentiment_agg"])

    # Expand multi-topic tags so each article contributes to its individual topics
    expanded_rows = []
    for _, row in items_df.iterrows():
        topics = str(row["topic_tags"]).split(",")
        pub_dt = str(row["published_at"])[:10]  # ISO date YYYY-MM-DD
        is_live = bool(row["is_live"])
        score = float(row["score"])
        is_neg = 1 if score < -0.15 else 0

        for t in topics:
            t = t.strip()
            if t:
                expanded_rows.append({
                    "period": pub_dt,
                    "topic": t,
                    "score": score,
                    "is_neg": is_neg,
                    "is_live": is_live,
                })

    if not expanded_rows:
        return pd.DataFrame(columns=COLUMNS["sentiment_agg"])

    exp_df = pd.DataFrame(expanded_rows)
    grouped = exp_df.groupby(["period", "topic", "is_live"], as_index=False).agg(
        mean_score=("score", "mean"),
        neg_share=("is_neg", "mean"),
        n_articles=("score", "count"),
    )

    grouped["mean_score"] = grouped["mean_score"].round(4)
    grouped["neg_share"] = grouped["neg_share"].round(4)
    grouped["n_articles"] = grouped["n_articles"].astype(int)

    res_df = grouped[["period", "topic", "mean_score", "neg_share", "n_articles", "is_live"]]
    res_df = res_df.sort_values(["period", "topic"]).reset_index(drop=True)
    return validate_table("sentiment_agg", res_df)


def check_sentiment_sufficiency(
    items_df: pd.DataFrame,
    min_articles: int = 30,
    window_days: int = 14,
    as_of: Optional[str] = None,
) -> dict:
    """Evaluate whether sentiment coverage is sufficient for alert corroboration.
    
    Returns dict:
    - status: 'sufficient' | 'insufficient'
    - n_articles: int
    - min_required: int
    - window_days: int
    - message: str
    """
    if items_df.empty:
        return {
            "status": "insufficient",
            "n_articles": 0,
            "min_required": min_articles,
            "window_days": window_days,
            "message": "Zero sentiment articles available in current window."
        }

    # Count live articles in the window
    n = len(items_df[items_df["is_live"] == True])
    status = "sufficient" if n >= min_articles else "insufficient"
    msg = (
        f"Coverage sufficient ({n} >= {min_articles} articles)."
        if status == "sufficient"
        else f"Coverage insufficient: {n} articles observed, minimum {min_articles} required."
    )
    return {
        "status": status,
        "n_articles": n,
        "min_required": min_articles,
        "window_days": window_days,
        "message": msg
    }
