# AI Stock Agent — Predictive Intelligence Platform

A locally-run **predictive intelligence platform** for Indian stock markets (NSE & BSE). Detects market-moving events from news, identifies impacted stocks, and generates forward-looking buy/sell signals with timing intelligence — all without any paid AI APIs.

## Features

### Intelligence Layer (NEW)
- **Event Detection**: Classifies 15+ event types — government contracts, defence orders, earnings beats/misses, RBI decisions, policy changes, regulatory actions, M&A, IPOs, geopolitical events
- **Entity Extraction**: 364-entry Nifty 500 company→ticker dictionary for automatic company name → NSE symbol mapping
- **Sector Correlation**: IT/Banking/Pharma/Defence/Railway/Energy sector spillover detection
- **Predictions Engine**: For each event, generates: direction (up/down), % move range, confidence score, action badge, timing window, and plain-English reasoning

### Timing Intelligence (NEW)
Every recommendation shows:
- **When to act**: "Buy at open (9:15–9:45 AM IST)" or "Wait 1–2h for direction confirmation"
- **Entry time window** (IST)
- **Stop-loss level** (% below entry)
- **Plain English reasoning** chain: news event → sector impact → recommendation

### Intelligence Feed Page (NEW)
- **Market Pulse**: -100 to +100 mood score updated every 5 minutes
- **Prediction cards** with action badges: BUY NOW / BUY AT OPEN / SELL AT OPEN / WATCH / WAIT / AVOID
- **Event feed** with impact level (high/medium/low) and sentiment hint
- Expandable "Why this stock?" reasoning panels
- Filter by signal type (buy/sell/watch) and minimum confidence %

### News Intelligence
- **23 RSS feeds**: Economic Times, Moneycontrol, LiveMint, Business Standard, Hindu Business Line, BBC
- News every **10 minutes** (down from 30 min)
- Entity extraction at ingestion time

### Existing Features
- **Watchlist & Holdings** management
- **Candlestick charts** with RSI, MACD, SMA
- **Buy/sell/hold signals** (rule-based)
- **Suggestions page** with buy/sell/potential stocks
- **Gainers/losers/most-active** (Nifty 50)

## Quick Start

### Windows
```bat
run.bat
```

### macOS / Linux
```bash
chmod +x run.sh && ./run.sh
```

### Manual
```bash
# Backend
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
export PYTHONPATH=.
uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** — click **⚡ Intelligence** in the nav bar.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/predictions` | GET | Today's predictions sorted by confidence |
| `/api/predictions/{ticker}` | GET | Predictions for a specific stock |
| `/api/events` | GET | Detected market-moving events |
| `/api/market-pulse` | GET | Market mood score + top signals |
| `/api/dashboard` | GET | Watchlist + signals + news aggregation |
| `/api/news` | GET | Recent news with sentiment |
| `/api/stocks` | GET | Prices and indicators |
| `/api/signals` | GET | Buy/sell/hold per ticker |
| `/api/watchlist` | GET/POST/DELETE | Manage watchlist |
| `/api/refresh` | POST | Trigger full refresh + prediction pipeline |
| `/api/stock/{ticker}` | GET | Stock detail with chart data + predictions |
| `/api/holdings` | GET/POST/DELETE | Portfolio holdings |
| `/api/market` | GET | Gainers, losers, most active (Nifty 50) |

## How Predictions Work

1. News is fetched from 23 RSS feeds every 10 minutes
2. Company names and tickers are extracted from each headline using a 364-entry Nifty 500 dictionary
3. Events are classified into 15 types (govt_contract, earnings_beat, rbi_decision, etc.)
4. Each event+ticker pair generates a prediction with:
   - Direction (up/down/neutral) and expected % move range
   - Confidence score (boosted by VADER sentiment)
   - Action badge (BUY NOW / BUY AT OPEN / SELL AT OPEN / WATCH / AVOID)
   - Timing window (when to enter/exit)
   - Stop-loss % recommendation
   - Plain English reasoning
5. Past predictions are stored for backtesting (fill `actual_outcome` column)

## Prediction Logic Examples

| Event | Typical Action | Expected Move | Entry Window |
|-------|---------------|---------------|--------------|
| Govt contract awarded | BUY AT OPEN | +2% to +6% | 9:15–9:45 AM IST |
| Defence order | BUY AT OPEN | +3% to +8% | 9:15–9:45 AM IST |
| Earnings beat | BUY AT OPEN | +2.5% to +8% | 9:15–9:45 AM IST |
| Earnings miss | SELL AT OPEN | -8% to -3% | 9:15–9:30 AM IST (exit) |
| RBI rate decision | WAIT | Varies | 11:00 AM–12:00 PM IST |
| Regulatory action | AVOID | -10% to -3% | Avoid 1–2 sessions |
| IPO listing | WATCH | +5% to +20% | 10:30–11:30 AM IST |

## Tech Stack

- **Backend**: FastAPI + SQLite + SQLAlchemy + APScheduler
- **NLP**: VADER sentiment + rule-based entity extraction
- **Data**: Yahoo Finance (yfinance) + 23 RSS news feeds
- **Frontend**: React 18 + TypeScript + Vite + TailwindCSS + React Query

## Disclaimer

Educational purposes only. Not financial advice. Past performance does not guarantee future results. All predictions are rule-based heuristics and carry significant uncertainty.
