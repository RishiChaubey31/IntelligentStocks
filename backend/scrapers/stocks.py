"""Stock price fetcher using yfinance."""
import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from backend.db.models import StockPrice, Watchlist, Holding
from backend.config import DEFAULT_WATCHLIST

logger = logging.getLogger(__name__)


def get_watchlist_tickers(db: Session) -> list[str]:
    """Get tickers from watchlist, or default if empty."""
    tickers = [w.ticker for w in db.query(Watchlist).all()]
    if not tickers:
        return DEFAULT_WATCHLIST
    return tickers


def _get_tickers_to_fetch(db: Session) -> list[str]:
    """Watchlist + holdings, deduplicated."""
    watch = set(get_watchlist_tickers(db))
    holdings = {h.ticker for h in db.query(Holding).all()}
    return list(watch | holdings)


def fetch_and_store_stocks(db: Session) -> int:
    """
    Fetch OHLCV data for watchlist + holdings and store in database.
    Returns number of price records stored.
    """
    tickers = _get_tickers_to_fetch(db)
    if not tickers:
        return 0

    count = 0
    end = datetime.utcnow()
    start = end - timedelta(days=60)  # 60 days of history for indicators

    try:
        for ticker in tickers:
            data = yf.download(
                ticker,
                start=start,
                end=end,
                progress=False,
                auto_adjust=True,
                threads=False,
            )

            if data.empty:
                continue

            df = data.copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            for date_idx, row in df.iterrows():
                if hasattr(date_idx, "to_pydatetime"):
                    dt = date_idx.to_pydatetime()
                else:
                    dt = datetime.combine(date_idx, datetime.min.time())

                # Get column names (yfinance varies)
                open_val = _get_col(row, "Open", "open")
                high_val = _get_col(row, "High", "high")
                low_val = _get_col(row, "Low", "low")
                close_val = _get_col(row, "Close", "close")
                vol_val = _get_col(row, "Volume", "volume")

                if close_val is None or (open_val is None and high_val is None and low_val is None):
                    continue

                # Use close for missing OHLC
                open_val = open_val or close_val
                high_val = high_val or close_val
                low_val = low_val or close_val
                vol_val = vol_val or 0

                existing = db.query(StockPrice).filter(
                    StockPrice.ticker == ticker,
                    StockPrice.date == dt,
                ).first()
                if existing:
                    continue

                db.add(StockPrice(
                    ticker=ticker,
                    date=dt,
                    open=float(open_val),
                    high=float(high_val),
                    low=float(low_val),
                    close=float(close_val),
                    volume=int(vol_val),
                ))
                count += 1

        db.commit()
    except Exception as e:
        logger.exception("Failed to fetch stock data: %s", e)
        db.rollback()

    return count


def _fetch_single_ticker(db: Session, ticker: str) -> int:
    """Fetch 60 days of OHLCV for a single ticker and store. Returns records added."""
    count = 0
    end = datetime.utcnow()
    start = end - timedelta(days=60)
    try:
        data = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True, threads=False)
        if data.empty:
            return 0
        df = data.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        for date_idx, row in df.iterrows():
            dt = date_idx.to_pydatetime() if hasattr(date_idx, "to_pydatetime") else datetime.combine(date_idx, datetime.min.time())
            open_val  = _get_col(row, "Open",   "open")
            high_val  = _get_col(row, "High",   "high")
            low_val   = _get_col(row, "Low",    "low")
            close_val = _get_col(row, "Close",  "close")
            vol_val   = _get_col(row, "Volume", "volume")
            if close_val is None:
                continue
            open_val = open_val or close_val
            high_val = high_val or close_val
            low_val  = low_val  or close_val
            existing = db.query(StockPrice).filter(StockPrice.ticker == ticker, StockPrice.date == dt).first()
            if existing:
                continue
            db.add(StockPrice(ticker=ticker, date=dt, open=float(open_val), high=float(high_val),
                              low=float(low_val), close=float(close_val), volume=int(vol_val or 0)))
            count += 1
        db.commit()
    except Exception as e:
        logger.warning("On-demand fetch failed for %s: %s", ticker, e)
        db.rollback()
    return count


def _get_col(row, *names):
    """Get value from row by possible column names."""
    for name in names:
        if name in row.index:
            val = row[name]
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                return val
    return None
