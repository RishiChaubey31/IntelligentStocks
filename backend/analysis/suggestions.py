"""Suggestion engine: buy/sell/potential based on news + technicals."""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.analysis.sentiment import get_ticker_sentiment, get_market_sentiment, _ticker_base
from backend.analysis.technical import get_indicators
from backend.config import NIFTY_50
from backend.db.models import Holding, News

logger = logging.getLogger(__name__)


@dataclass
class BuySuggestion:
    ticker: str
    symbol: str
    reason: str
    confidence: float
    sentiment: float
    rsi: float | None
    news_count: int


@dataclass
class SellSuggestion:
    ticker: str
    symbol: str
    reason: str
    confidence: float
    sentiment: float
    rsi: float | None
    news: list[dict]


@dataclass
class PotentialStock:
    ticker: str
    symbol: str
    rationale: str
    score: float


def get_related_news(db: Session, ticker: str, limit: int = 5) -> list[dict]:
    """Get recent news mentioning this ticker."""
    base = _ticker_base(ticker)
    cutoff = datetime.utcnow() - timedelta(days=2)
    items = db.query(News).filter(
        News.tickers.isnot(None),
        News.published_at >= cutoff,
    ).order_by(News.published_at.desc()).limit(200).all()

    result = []
    for n in items:
        if n.tickers and base in [t.strip().upper() for t in n.tickers.split(",")]:
            result.append({
                "id": n.id,
                "title": n.title,
                "link": n.link,
                "source": n.source,
                "category": n.category,
                "sentiment_score": n.sentiment_score,
            })
            if len(result) >= limit:
                break
    return result


def compute_suggestions(db: Session) -> dict:
    """
    Compute buy suggestions, sell suggestions (for holdings), and stocks with potential.
    Returns { buy_suggestions, sell_suggestions, potential_stocks }
    """
    holdings = db.query(Holding).all()
    holding_tickers = {h.ticker for h in holdings}

    # All tickers to consider: Nifty 50 + holdings
    tickers = list(dict.fromkeys(NIFTY_50[:30] + list(holding_tickers)))

    buy_suggestions = []
    sell_suggestions = []
    potential_stocks = []

    market_sentiment = get_market_sentiment(db)

    for ticker in tickers:
        ind = get_indicators(db, ticker)
        if not ind:
            continue

        # Sentiment from all categories
        sentiment = get_ticker_sentiment(db, ticker, days=2) or market_sentiment
        rsi = ind.get("rsi")
        macd = ind.get("macd_signal")
        trend = ind.get("trend", "neutral")
        symbol = ticker.replace(".NS", "").replace(".BO", "")

        buy_score = 0
        sell_score = 0
        reasons = []

        # RSI
        if rsi is not None:
            if rsi < 30:
                buy_score += 2
                reasons.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > 70:
                sell_score += 2
                reasons.append(f"RSI overbought ({rsi:.1f})")
            elif rsi < 40:
                buy_score += 1
            elif rsi > 60:
                sell_score += 1

        # Sentiment
        if sentiment > 0.1:
            buy_score += 1
            reasons.append(f"positive sentiment ({sentiment:.2f})")
        elif sentiment < -0.1:
            sell_score += 1
            reasons.append(f"negative sentiment ({sentiment:.2f})")

        # MACD
        if macd == "bullish":
            buy_score += 1
            reasons.append("MACD bullish")
        elif macd == "bearish":
            sell_score += 1
            reasons.append("MACD bearish")

        # Trend
        if trend == "up":
            buy_score += 0.5
        elif trend == "down":
            sell_score += 0.5

        reason_str = "; ".join(reasons) if reasons else "No strong signals"
        confidence = min(90, 40 + max(buy_score, sell_score) * 10)

        # Sell suggestions for holdings
        if ticker in holding_tickers and (sell_score >= 2 or sell_score > buy_score):
            news = get_related_news(db, ticker, limit=5)
            sell_suggestions.append(SellSuggestion(
                ticker=ticker,
                symbol=symbol,
                reason=reason_str,
                confidence=confidence,
                sentiment=sentiment,
                rsi=rsi,
                news=news,
            ))

        # Buy suggestions (strong buy signal)
        elif buy_score >= 3 and buy_score > sell_score:
            news_count = len(get_related_news(db, ticker, limit=10))
            buy_suggestions.append(BuySuggestion(
                ticker=ticker,
                symbol=symbol,
                reason=reason_str,
                confidence=confidence,
                sentiment=sentiment,
                rsi=rsi,
                news_count=news_count,
            ))

        # Potential stocks (weaker buy signal)
        elif buy_score >= 1.5 and buy_score > sell_score:
            potential_stocks.append(PotentialStock(
                ticker=ticker,
                symbol=symbol,
                rationale=reason_str,
                score=confidence,
            ))

    # Sort and limit
    buy_suggestions.sort(key=lambda x: x.confidence, reverse=True)
    potential_stocks.sort(key=lambda x: x.score, reverse=True)

    return {
        "buy_suggestions": [
            {
                "ticker": x.ticker,
                "symbol": x.symbol,
                "reason": x.reason,
                "confidence": x.confidence,
                "sentiment": x.sentiment,
                "rsi": x.rsi,
                "news_count": x.news_count,
            }
            for x in buy_suggestions[:10]
        ],
        "sell_suggestions": [
            {
                "ticker": x.ticker,
                "symbol": x.symbol,
                "reason": x.reason,
                "confidence": x.confidence,
                "sentiment": x.sentiment,
                "rsi": x.rsi,
                "news": x.news,
            }
            for x in sell_suggestions[:10]
        ],
        "potential_stocks": [
            {
                "ticker": x.ticker,
                "symbol": x.symbol,
                "rationale": x.rationale,
                "score": x.score,
            }
            for x in potential_stocks[:15]
        ],
    }
