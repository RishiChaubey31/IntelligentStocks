"""Technical indicators: RSI, MACD, SMA."""
import logging
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from backend.db.models import StockPrice

logger = logging.getLogger(__name__)


def get_price_df(db: Session, ticker: str, days: int = 60) -> pd.DataFrame | None:
    """Get OHLCV DataFrame for a ticker."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = db.query(StockPrice).filter(
        StockPrice.ticker == ticker,
        StockPrice.date >= cutoff,
    ).order_by(StockPrice.date).all()

    if len(rows) < 14:  # Need at least 14 for RSI
        return None

    df = pd.DataFrame([
        {
            "date": r.date,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume or 0,
        }
        for r in rows
    ])
    df.set_index("date", inplace=True)
    df.sort_index(inplace=True)
    return df


def compute_rsi(series: pd.Series, period: int = 14) -> float | None:
    """Compute RSI. Returns None if insufficient data."""
    if len(series) < period + 1:
        return None
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None


def compute_macd_signal(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> str | None:
    """
    Compute MACD. Returns 'bullish', 'bearish', or 'neutral'.
    Bullish = MACD line crosses above signal. Bearish = MACD line crosses below signal.
    """
    if len(series) < slow + signal:
        return None
    try:
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line

        # Last two values to detect crossover
        if len(hist) < 2:
            return None
        prev, curr = hist.iloc[-2], hist.iloc[-1]
        if prev < 0 and curr > 0:
            return "bullish"
        if prev > 0 and curr < 0:
            return "bearish"
        return "neutral"
    except Exception:
        return None


def compute_sma(series: pd.Series, period: int) -> float | None:
    """Compute simple moving average."""
    if len(series) < period:
        return None
    sma = series.rolling(window=period).mean()
    val = sma.iloc[-1]
    return float(val) if not pd.isna(val) else None


def get_indicators(db: Session, ticker: str) -> dict | None:
    """
    Get all technical indicators for a ticker.
    Returns dict with rsi, macd_signal, sma_20, sma_50, current_price, trend.
    """
    df = get_price_df(db, ticker)
    if df is None or df.empty:
        return None

    close = df["close"]
    return {
        "ticker": ticker,
        "current_price": float(close.iloc[-1]),
        "rsi": compute_rsi(close),
        "macd_signal": compute_macd_signal(close),
        "sma_20": compute_sma(close, 20),
        "sma_50": compute_sma(close, 50),
        "trend": _get_trend(close),
    }


def _get_trend(close: pd.Series) -> str:
    """Simple trend: up if price above SMA20, down if below."""
    if len(close) < 20:
        return "neutral"
    sma20 = close.rolling(20).mean().iloc[-1]
    return "up" if close.iloc[-1] > sma20 else "down"
