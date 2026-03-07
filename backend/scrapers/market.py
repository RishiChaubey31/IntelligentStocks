"""Fetch NSE gainers, losers, most active stocks via yfinance."""
import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from backend.config import NIFTY_50

logger = logging.getLogger(__name__)


def fetch_gainers_losers_active(limit: int = 20) -> dict:
    """
    Fetch today's top gainers, losers, and most active from Nifty 50.
    Returns dict with gainers, losers, most_active lists.
    """
    end = datetime.utcnow()
    start = end - timedelta(days=5)
    results = []

    for ticker in NIFTY_50[:40]:
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
            if df is None or df.empty or len(df) < 2:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close = df["Close"] if "Close" in df.columns else df.get("close")
            if close is None:
                continue
            prev_close = close.iloc[-2]
            curr_close = close.iloc[-1]
            if pd.isna(prev_close) or pd.isna(curr_close) or prev_close == 0:
                continue
            pct_change = ((curr_close - prev_close) / prev_close) * 100
            vol = df["Volume"].iloc[-1] if "Volume" in df.columns else 0
            if pd.isna(vol):
                vol = 0
            value_traded = float(curr_close * vol) if vol else 0
            display = ticker.replace(".NS", "").replace(".BO", "")
            results.append({
                "ticker": ticker,
                "symbol": display,
                "price": float(curr_close),
                "change_pct": round(float(pct_change), 2),
                "volume": int(vol),
                "value_traded": round(value_traded, 0),
            })
        except Exception:
            continue

    # Sort and slice
    gainers = sorted(results, key=lambda x: x["change_pct"], reverse=True)[:limit]
    losers = sorted(results, key=lambda x: x["change_pct"])[:limit]
    most_active = sorted(results, key=lambda x: x["value_traded"], reverse=True)[:limit]

    return {"gainers": gainers, "losers": losers, "most_active": most_active}
