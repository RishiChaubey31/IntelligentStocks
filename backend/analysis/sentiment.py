"""Sentiment analysis using VADER on news headlines."""
import re
import logging
from datetime import datetime, timedelta

import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from sqlalchemy.orm import Session

from backend.db.models import News

logger = logging.getLogger(__name__)


def _ensure_vader():
    """Download VADER lexicon if not present."""
    try:
        nltk.data.find("sentiment/vader_lexicon.zip")
    except LookupError:
        nltk.download("vader_lexicon", quiet=True)


def extract_tickers(text: str) -> list[str]:
    """Extract ticker symbols using the comprehensive entity extractor."""
    from backend.intelligence.entity_extractor import extract_entities
    return extract_entities(text)


def analyze_news_sentiment(db: Session) -> int:
    """
    Run VADER on news headlines that don't have sentiment yet.
    Update sentiment_score and tickers. Returns count updated.
    """
    _ensure_vader()
    sid = SentimentIntensityAnalyzer()

    cutoff = datetime.utcnow() - timedelta(days=7)
    news_items = db.query(News).filter(
        News.sentiment_score.is_(None),
        News.published_at >= cutoff,
    ).all()

    count = 0
    for news in news_items:
        text = f"{news.title} {news.summary or ''}"
        scores = sid.polarity_scores(text)
        news.sentiment_score = scores["compound"]

        # Only update tickers if not already set by the scraper
        if not news.tickers:
            tickers = extract_tickers(text)
            news.tickers = ",".join(tickers) if tickers else None
        count += 1

    db.commit()
    return count


def _ticker_base(ticker: str) -> str:
    """Get base ticker without exchange suffix for news matching."""
    t = ticker.upper()
    for suffix in (".NS", ".BO"):
        if t.endswith(suffix):
            return t[: -len(suffix)]
    return t


def get_ticker_sentiment(
    db: Session,
    ticker: str,
    days: int = 7,
    categories: list[str] | None = None,
) -> float | None:
    """Get average sentiment for a ticker over the last N days."""
    base = _ticker_base(ticker)
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = db.query(News).filter(
        News.tickers.isnot(None),
        News.sentiment_score.isnot(None),
        News.published_at >= cutoff,
    )
    if categories:
        q = q.filter(News.category.in_(categories))
    items = q.all()

    scores = []
    for n in items:
        if n.tickers and base in [t.strip().upper() for t in n.tickers.split(",")]:
            scores.append(n.sentiment_score)

    if not scores:
        return None
    return sum(scores) / len(scores)


def get_market_sentiment(db: Session, days: int = 7) -> float:
    """Get overall market sentiment (average of all news)."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    items = db.query(News).filter(
        News.sentiment_score.isnot(None),
        News.published_at >= cutoff,
    ).all()

    if not items:
        return 0.0
    return sum(n.sentiment_score for n in items) / len(items)
