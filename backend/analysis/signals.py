"""Signal rule engine: buy/sell/hold based on sentiment + technicals."""
import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from backend.analysis.sentiment import get_ticker_sentiment, get_market_sentiment
from backend.analysis.technical import get_indicators
from backend.db.models import Signal
from backend.scrapers.stocks import get_watchlist_tickers

logger = logging.getLogger(__name__)

SignalType = Literal["buy", "sell", "hold"]


@dataclass
class SignalResult:
    ticker: str
    signal: SignalType
    confidence: float
    reason: str
    rsi: float | None
    sentiment: float | None
    macd_signal: str | None


# Configurable thresholds
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
SENTIMENT_POSITIVE = 0.1
SENTIMENT_NEGATIVE = -0.1


def compute_signals(db: Session) -> list[SignalResult]:
    """
    Compute buy/sell/hold for each ticker in watchlist.
    Returns list of SignalResult.
    """
    tickers = get_watchlist_tickers(db)
    results = []

    market_sentiment = get_market_sentiment(db)

    for ticker in tickers:
        indicators = get_indicators(db, ticker)
        if not indicators:
            continue

        ticker_sentiment = get_ticker_sentiment(db, ticker) or market_sentiment
        rsi = indicators.get("rsi")
        macd = indicators.get("macd_signal")


        # Rule engine
        signal, confidence, reason = _evaluate(
            rsi=rsi,
            sentiment=ticker_sentiment,
            macd=macd,
            trend=indicators.get("trend", "neutral"),
        )

        results.append(SignalResult(
            ticker=ticker,
            signal=signal,
            confidence=confidence,
            reason=reason,
            rsi=rsi,
            sentiment=ticker_sentiment,
            macd_signal=macd,
        ))

    return results


def _evaluate(
    rsi: float | None,
    sentiment: float,
    macd: str | None,
    trend: str,
) -> tuple[SignalType, float, str]:
    """Evaluate rules and return (signal, confidence, reason)."""
    reasons = []
    buy_score = 0
    sell_score = 0

    # RSI signals
    if rsi is not None:
        if rsi < RSI_OVERSOLD:
            buy_score += 2
            reasons.append(f"RSI oversold ({rsi:.2f})")
        elif rsi > RSI_OVERBOUGHT:
            sell_score += 2
            reasons.append(f"RSI overbought ({rsi:.2f})")
        elif rsi < 40:
            buy_score += 1
            reasons.append(f"RSI low ({rsi:.2f})")
        elif rsi > 60:
            sell_score += 1
            reasons.append(f"RSI high ({rsi:.2f})")

    # Sentiment signals
    if sentiment > SENTIMENT_POSITIVE:
        buy_score += 1
        reasons.append(f"positive sentiment ({sentiment:.2f})")
    elif sentiment < SENTIMENT_NEGATIVE:
        sell_score += 1
        reasons.append(f"negative sentiment ({sentiment:.2f})")

    # MACD signals
    if macd == "bullish":
        buy_score += 1
        reasons.append("MACD bullish crossover")
    elif macd == "bearish":
        sell_score += 1
        reasons.append("MACD bearish crossover")

    # Trend
    if trend == "up":
        buy_score += 0.5
    elif trend == "down":
        sell_score += 0.5

    # Determine signal
    if buy_score >= 3 and buy_score > sell_score:
        signal = "buy"
        confidence = min(90, 50 + buy_score * 10)
    elif sell_score >= 3 and sell_score > buy_score:
        signal = "sell"
        confidence = min(90, 50 + sell_score * 10)
    else:
        signal = "hold"
        confidence = 40 + max(buy_score, sell_score) * 5

    reason = "; ".join(reasons) if reasons else "No strong signals"
    return signal, confidence, reason


def store_signals(db: Session, results: list[SignalResult]) -> None:
    """Store computed signals in database."""
    for r in results:
        db.add(Signal(
            ticker=r.ticker,
            signal=r.signal,
            confidence=r.confidence,
            reason=r.reason,
            rsi=r.rsi,
            sentiment=r.sentiment,
            macd_signal=r.macd_signal,
        ))
    db.commit()


def get_latest_signals(db: Session) -> list[dict]:
    """Get most recent signal per ticker."""
    all_signals = db.query(Signal).order_by(Signal.created_at.desc()).all()
    seen = set()
    signals = []
    for s in all_signals:
        if s.ticker not in seen:
            seen.add(s.ticker)
            signals.append(s)

    return [
        {
            "ticker": s.ticker,
            "signal": s.signal,
            "confidence": s.confidence,
            "reason": s.reason,
            "rsi": s.rsi,
            "sentiment": s.sentiment,
            "macd_signal": s.macd_signal,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in signals
    ]
