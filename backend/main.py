"""FastAPI application for AI Stock Agent."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.config import (
    FRONTEND_URL,
    NEWS_SCRAPE_INTERVAL,
    STOCK_SCRAPE_INTERVAL,
    to_yahoo_ticker,
    to_display_ticker,
)
from backend.db import get_db, init_db
from backend.scrapers import (
    fetch_and_store_news,
    fetch_and_store_stocks,
    get_watchlist_tickers,
    fetch_gainers_losers_active,
)
from backend.analysis import (
    analyze_news_sentiment,
    compute_signals,
    store_signals,
    get_latest_signals,
    get_indicators,
    get_market_sentiment,
    compute_suggestions,
)
from backend.db.models import News, StockPrice, Watchlist, Holding, Prediction, MarketEvent
from backend.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    init_db()
    start_scheduler()
    # Preload NSE equity master in background so search is fast
    try:
        from backend.scrapers.nse import preload_equity_master
        import threading
        threading.Thread(target=preload_equity_master, daemon=True).start()
    except Exception:
        pass
    yield
    stop_scheduler()


app = FastAPI(
    title="AI Stock Agent",
    description="Local stock signal system from news and technical analysis",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic models ---
class WatchlistAdd(BaseModel):
    ticker: str


class WatchlistRemove(BaseModel):
    ticker: str


class HoldingAdd(BaseModel):
    ticker: str
    quantity: int
    buy_price: float
    notes: str | None = None


# --- API Routes ---

@app.get("/api/news")
def api_news(db: Session = Depends(get_db), limit: int = 50):
    """Recent news with sentiment."""
    items = db.query(News).order_by(News.published_at.desc()).limit(limit).all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "link": n.link,
            "source": n.source,
            "category": n.category,
            "published_at": n.published_at.isoformat() if n.published_at else None,
            "summary": n.summary,
            "sentiment_score": n.sentiment_score,
            "tickers": n.tickers.split(",") if n.tickers else [],
        }
        for n in items
    ]


@app.get("/api/stocks")
def api_stocks(db: Session = Depends(get_db)):
    """Current prices and indicators for watchlist."""
    tickers = get_watchlist_tickers(db)
    result = []
    for ticker in tickers:
        ind = get_indicators(db, ticker)
        if ind:
            result.append(ind)
    return result


@app.get("/api/signals")
def api_signals(db: Session = Depends(get_db)):
    """Latest buy/sell/hold signals per ticker."""
    signals = get_latest_signals(db)
    if not signals:
        # Compute fresh if none stored
        results = compute_signals(db)
        store_signals(db, results)
        signals = get_latest_signals(db)
    return signals


@app.get("/api/dashboard")
def api_dashboard(db: Session = Depends(get_db)):
    """Aggregated view: watchlist, signals, recent news, market sentiment."""
    tickers = get_watchlist_tickers(db)
    signals = get_latest_signals(db)
    if not signals:
        results = compute_signals(db)
        store_signals(db, results)
        signals = get_latest_signals(db)

    news = db.query(News).order_by(News.published_at.desc()).limit(10).all()
    market_sentiment = get_market_sentiment(db)

    return {
        "watchlist": tickers,
        "signals": signals,
        "news": [
            {
                "id": n.id,
                "title": n.title,
                "link": n.link,
                "source": n.source,
                "sentiment_score": n.sentiment_score,
            }
            for n in news
        ],
        "market_sentiment": market_sentiment,
    }


@app.post("/api/watchlist")
def api_watchlist_add(item: WatchlistAdd, db: Session = Depends(get_db)):
    """Add ticker to watchlist. Auto-appends .NS (NSE) if no exchange suffix."""
    ticker = to_yahoo_ticker(item.ticker)
    if not ticker or len(ticker) > 16:
        raise HTTPException(400, "Invalid ticker")
    existing = db.query(Watchlist).filter(Watchlist.ticker == ticker).first()
    if existing:
        return {"status": "already_exists", "ticker": ticker}
    db.add(Watchlist(ticker=ticker))
    db.commit()
    return {"status": "added", "ticker": ticker}


@app.delete("/api/watchlist/{ticker}")
def api_watchlist_remove(ticker: str, db: Session = Depends(get_db)):
    """Remove ticker from watchlist."""
    ticker = to_yahoo_ticker(ticker)
    w = db.query(Watchlist).filter(Watchlist.ticker == ticker).first()
    if not w:
        raise HTTPException(404, "Ticker not in watchlist")
    db.delete(w)
    db.commit()
    return {"status": "removed", "ticker": ticker}


@app.get("/api/watchlist")
def api_watchlist(db: Session = Depends(get_db)):
    """Get current watchlist (Yahoo symbols for API, display names in UI)."""
    return [w.ticker for w in db.query(Watchlist).all()]


@app.post("/api/refresh")
def api_refresh(db: Session = Depends(get_db)):
    """Trigger manual scrape, recompute signals, and run prediction pipeline."""
    from backend.intelligence.predictor import run_prediction_pipeline
    news_count = fetch_and_store_news(db)
    stock_count = fetch_and_store_stocks(db)
    sentiment_count = analyze_news_sentiment(db)
    results = compute_signals(db)
    store_signals(db, results)
    prediction_count = run_prediction_pipeline(db)
    return {
        "news_fetched": news_count,
        "stock_records": stock_count,
        "sentiment_updated": sentiment_count,
        "signals_computed": len(results),
        "predictions_generated": prediction_count,
    }


@app.get("/api/stock/{ticker}")
def api_stock_detail(ticker: str, db: Session = Depends(get_db)):
    """Stock detail: indicators, price history, related news.
    Fetches price data on-demand if the ticker isn't yet in the DB.
    """
    ticker = ticker.upper()
    # Normalise: strip exchange suffix, then re-add .NS
    from backend.config import to_yahoo_ticker
    ticker = to_yahoo_ticker(ticker.replace(".NS", "").replace(".BO", ""))

    ind = get_indicators(db, ticker)
    if not ind:
        # On-demand fetch: pull 60 days of price history right now
        try:
            from backend.scrapers.stocks import _fetch_single_ticker
            _fetch_single_ticker(db, ticker)
            ind = get_indicators(db, ticker)
        except Exception:
            pass

    # If still no data, try NSE live quote as minimal fallback
    nse_quote = None
    if not ind:
        try:
            from backend.scrapers.nse import get_nse_quote
            base = ticker.replace(".NS", "").replace(".BO", "")
            nse_quote = get_nse_quote(base)
            if nse_quote and nse_quote.get("last_price"):
                ind = {
                    "ticker": ticker,
                    "current_price": nse_quote["last_price"],
                    "rsi": None,
                    "macd_signal": None,
                    "sma_20": None,
                    "sma_50": None,
                    "trend": "neutral",
                }
        except Exception:
            pass

    if not ind:
        raise HTTPException(404, f"No data for {ticker}. Try adding it to your watchlist first.")

    # Price history for chart
    prices = db.query(StockPrice).filter(
        StockPrice.ticker == ticker,
    ).order_by(StockPrice.date).all()

    # Related news (match base ticker, e.g. RELIANCE from RELIANCE.NS)
    from backend.analysis.sentiment import _ticker_base
    base_ticker = _ticker_base(ticker)
    news = db.query(News).filter(
        News.tickers.isnot(None),
    ).order_by(News.published_at.desc()).limit(200).all()
    news = [n for n in news if n.tickers and base_ticker in [t.strip().upper() for t in n.tickers.split(",")]][:10]

    from backend.db.models import Signal
    sig = db.query(Signal).filter(Signal.ticker == ticker).order_by(Signal.created_at.desc()).first()

    return {
        "ticker": ticker,
        "indicators": ind,
        "price_history": [
            {"date": p.date.isoformat(), "open": p.open, "high": p.high, "low": p.low, "close": p.close}
            for p in prices[-60:]
        ],
        "news": [
            {"id": n.id, "title": n.title, "link": n.link, "source": n.source, "sentiment_score": n.sentiment_score}
            for n in news
        ],
        "signal": {
            "signal": sig.signal,
            "confidence": sig.confidence,
            "reason": sig.reason,
        } if sig else None,
    }


@app.get("/api/ipos")
def api_ipos(db: Session = Depends(get_db), limit: int = 20):
    """Latest IPO news from RSS feeds."""
    items = db.query(News).filter(
        News.category == "ipo",
    ).order_by(News.published_at.desc()).limit(limit).all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "link": n.link,
            "source": n.source,
            "published_at": n.published_at.isoformat() if n.published_at else None,
            "summary": n.summary,
            "sentiment_score": n.sentiment_score,
        }
        for n in items
    ]


@app.get("/api/market")
def api_market(limit: int = 15):
    """Today's gainers, losers, and most active stocks (Nifty 50)."""
    return fetch_gainers_losers_active(limit=limit)


@app.get("/api/companies")
def api_companies():
    """List of NSE/BSE companies (Nifty 50)."""
    from backend.config import NIFTY_50
    return [
        {"ticker": t, "symbol": t.replace(".NS", "").replace(".BO", "")}
        for t in NIFTY_50
    ]


@app.get("/api/holdings")
def api_holdings(db: Session = Depends(get_db)):
    """List all holdings with current price."""
    holdings = db.query(Holding).order_by(Holding.created_at.desc()).all()
    result = []
    for h in holdings:
        ind = get_indicators(db, h.ticker)
        current_price = ind["current_price"] if ind else h.buy_price
        pnl_pct = ((current_price - h.buy_price) / h.buy_price * 100) if h.buy_price else 0
        result.append({
            "id": h.id,
            "ticker": h.ticker,
            "quantity": h.quantity,
            "buy_price": h.buy_price,
            "buy_date": h.buy_date.isoformat() if h.buy_date else None,
            "notes": h.notes,
            "current_price": current_price,
            "pnl_pct": round(pnl_pct, 2),
        })
    return result


@app.post("/api/holdings")
def api_holdings_add(item: HoldingAdd, db: Session = Depends(get_db)):
    """Add a holding."""
    ticker = to_yahoo_ticker(item.ticker)
    if not ticker or item.quantity <= 0 or item.buy_price <= 0:
        raise HTTPException(400, "Invalid input")
    db.add(Holding(ticker=ticker, quantity=item.quantity, buy_price=item.buy_price, notes=item.notes))
    db.commit()
    return {"status": "added", "ticker": ticker}


@app.get("/api/suggestions")
def api_suggestions(db: Session = Depends(get_db)):
    """Buy/sell suggestions and stocks with potential."""
    return compute_suggestions(db)


@app.delete("/api/holdings/{holding_id}")
def api_holdings_remove(holding_id: int, db: Session = Depends(get_db)):
    """Remove a holding."""
    h = db.query(Holding).filter(Holding.id == holding_id).first()
    if not h:
        raise HTTPException(404, "Holding not found")
    db.delete(h)
    db.commit()
    return {"status": "removed", "id": holding_id}


@app.get("/api/predictions")
def api_predictions(db: Session = Depends(get_db), limit: int = 50, min_confidence: float = 40):
    """Today's predictions sorted by confidence."""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(hours=48)
    preds = (
        db.query(Prediction)
        .filter(Prediction.created_at >= cutoff, Prediction.confidence >= min_confidence)
        .order_by(Prediction.confidence.desc(), Prediction.created_at.desc())
        .limit(limit)
        .all()
    )

    seen: set[str] = set()
    result = []
    for p in preds:
        key = f"{p.ticker}:{p.event_type}"
        if key in seen:
            continue
        seen.add(key)

        news = db.query(News).filter(News.id == p.news_id).first() if p.news_id else None
        result.append({
            "id": p.id,
            "ticker": p.ticker,
            "symbol": p.ticker.replace(".NS", "").replace(".BO", ""),
            "event_type": p.event_type,
            "predicted_direction": p.predicted_direction,
            "predicted_pct_low": p.predicted_pct_low,
            "predicted_pct_high": p.predicted_pct_high,
            "confidence": p.confidence,
            "action": p.action,
            "timing_window": p.timing_window,
            "entry_time": p.entry_time,
            "stop_loss_pct": p.stop_loss_pct,
            "reasoning": p.reasoning,
            "sector_impact": p.sector_impact.split(",") if p.sector_impact else [],
            "affected_tickers": p.affected_tickers.split(",") if p.affected_tickers else [],
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "news": {
                "id": news.id,
                "title": news.title,
                "link": news.link,
                "source": news.source,
                "published_at": news.published_at.isoformat() if news.published_at else None,
            } if news else None,
        })

    return result


@app.get("/api/predictions/{ticker}")
def api_predictions_ticker(ticker: str, db: Session = Depends(get_db)):
    """Predictions for a specific stock ticker."""
    from datetime import datetime, timedelta
    ticker = ticker.upper()
    base = ticker.replace(".NS", "").replace(".BO", "")

    cutoff = datetime.utcnow() - timedelta(hours=72)
    preds = (
        db.query(Prediction)
        .filter(
            Prediction.ticker == base,
            Prediction.created_at >= cutoff,
        )
        .order_by(Prediction.confidence.desc(), Prediction.created_at.desc())
        .limit(10)
        .all()
    )

    result = []
    for p in preds:
        news = db.query(News).filter(News.id == p.news_id).first() if p.news_id else None
        result.append({
            "id": p.id,
            "ticker": p.ticker,
            "event_type": p.event_type,
            "predicted_direction": p.predicted_direction,
            "predicted_pct_low": p.predicted_pct_low,
            "predicted_pct_high": p.predicted_pct_high,
            "confidence": p.confidence,
            "action": p.action,
            "timing_window": p.timing_window,
            "entry_time": p.entry_time,
            "stop_loss_pct": p.stop_loss_pct,
            "reasoning": p.reasoning,
            "sector_impact": p.sector_impact.split(",") if p.sector_impact else [],
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "news": {
                "id": news.id,
                "title": news.title,
                "link": news.link,
                "source": news.source,
                "published_at": news.published_at.isoformat() if news.published_at else None,
            } if news else None,
        })

    return result


@app.get("/api/events")
def api_events(db: Session = Depends(get_db), limit: int = 50, impact: str | None = None):
    """Detected market-moving events, newest first."""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(hours=48)
    q = db.query(MarketEvent).filter(MarketEvent.published_at >= cutoff)
    if impact:
        q = q.filter(MarketEvent.impact == impact)
    events = q.order_by(MarketEvent.published_at.desc()).limit(limit).all()

    return [
        {
            "id": e.id,
            "news_id": e.news_id,
            "event_type": e.event_type,
            "impact": e.impact,
            "affected_tickers": e.affected_tickers.split(",") if e.affected_tickers else [],
            "affected_sectors": e.affected_sectors.split(",") if e.affected_sectors else [],
            "sentiment_hint": e.sentiment_hint,
            "keywords": e.keywords.split(",") if e.keywords else [],
            "title": e.title,
            "source": e.source,
            "published_at": e.published_at.isoformat() if e.published_at else None,
        }
        for e in events
    ]


@app.get("/api/market-pulse")
def api_market_pulse(db: Session = Depends(get_db)):
    """Overall market mood score for today."""
    from datetime import datetime, timedelta
    from backend.analysis.sentiment import get_market_sentiment

    cutoff_6h = datetime.utcnow() - timedelta(hours=6)
    cutoff_24h = datetime.utcnow() - timedelta(hours=24)

    # Recent news
    recent_news = db.query(News).filter(News.published_at >= cutoff_6h).all()
    day_news = db.query(News).filter(News.published_at >= cutoff_24h).all()

    # High-impact events today
    high_events = db.query(MarketEvent).filter(
        MarketEvent.published_at >= cutoff_24h,
        MarketEvent.impact == "high",
    ).count()

    positive_events = db.query(MarketEvent).filter(
        MarketEvent.published_at >= cutoff_24h,
        MarketEvent.sentiment_hint == "positive",
    ).count()

    negative_events = db.query(MarketEvent).filter(
        MarketEvent.published_at >= cutoff_24h,
        MarketEvent.sentiment_hint == "negative",
    ).count()

    # Sentiment scores
    sentiment_scores = [n.sentiment_score for n in day_news if n.sentiment_score is not None]
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0

    # Compute mood: -100 (very bearish) to +100 (very bullish)
    mood_score = avg_sentiment * 100
    mood_score += (positive_events - negative_events) * 5
    mood_score = max(-100, min(100, mood_score))

    if mood_score > 20:
        mood_label = "Bullish"
        mood_color = "green"
    elif mood_score > 5:
        mood_label = "Mildly Bullish"
        mood_color = "green"
    elif mood_score < -20:
        mood_label = "Bearish"
        mood_color = "red"
    elif mood_score < -5:
        mood_label = "Mildly Bearish"
        mood_color = "red"
    else:
        mood_label = "Neutral"
        mood_color = "yellow"

    # Top predictions for today
    top_preds = (
        db.query(Prediction)
        .filter(Prediction.created_at >= cutoff_24h, Prediction.confidence >= 60)
        .order_by(Prediction.confidence.desc())
        .limit(5)
        .all()
    )

    return {
        "mood_score": round(mood_score, 1),
        "mood_label": mood_label,
        "mood_color": mood_color,
        "avg_sentiment": round(avg_sentiment, 3),
        "news_count_6h": len(recent_news),
        "news_count_24h": len(day_news),
        "high_impact_events": high_events,
        "positive_events": positive_events,
        "negative_events": negative_events,
        "top_predictions": [
            {
                "ticker": p.ticker,
                "symbol": p.ticker.replace(".NS", "").replace(".BO", ""),
                "action": p.action,
                "confidence": p.confidence,
                "predicted_direction": p.predicted_direction,
                "event_type": p.event_type,
            }
            for p in top_preds
        ],
    }


@app.get("/api/search")
def api_search(q: str = "", limit: int = 15):
    """
    Search ALL NSE/BSE listed stocks by name or symbol.
    Sources data directly from NSE India — covers every listed equity, ETF, bond, SME stock.
    """
    from backend.scrapers.nse import search_nse
    if not q or len(q.strip()) < 1:
        return []
    results = search_nse(q.strip(), limit=limit)
    return results


@app.get("/api/quote/{symbol}")
def api_quote(symbol: str):
    """
    Live quote for any NSE stock directly from NSE India.
    Symbol format: RELIANCE or RELIANCE.NS (suffix ignored).
    """
    from backend.scrapers.nse import get_nse_quote
    symbol = symbol.upper().replace(".NS", "").replace(".BO", "")
    quote = get_nse_quote(symbol)
    if not quote:
        raise HTTPException(404, f"No live quote found for {symbol} on NSE")
    return quote


@app.get("/api/nse-market")
def api_nse_market():
    """Gainers and losers directly from NSE India."""
    from backend.scrapers.nse import get_nse_gainers_losers
    return get_nse_gainers_losers(limit=15)


@app.get("/api/health")
def health():
    """Health check."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Gemini AI endpoints
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str


@app.get("/api/ai/analysis")
def api_ai_analysis(db: Session = Depends(get_db)):
    """Gemini AI stock analysis: buy/sell picks based on live news + signals."""
    from backend.intelligence.gemini_agent import get_ai_stock_analysis
    return get_ai_stock_analysis(db)


@app.post("/api/ai/chat")
def api_ai_chat(req: ChatRequest, db: Session = Depends(get_db)):
    """Chat with Gemini AI about stocks — answers any question using live market context."""
    from backend.intelligence.gemini_agent import chat_with_ai
    reply = chat_with_ai(req.message, db)
    return {"reply": reply}
