"""Configuration for the AI Stock Agent."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Gemini AI — loaded from .env (GEMINI_API_KEY=your_key)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "stock_agent.db"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Indian stock market (NSE & BSE only)
# Yahoo Finance: .NS = NSE, .BO = BSE
DEFAULT_WATCHLIST = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS",
    "HINDUNILVR.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "WIPRO.NS",
    "HCLTECH.NS", "BAJFINANCE.NS", "TITAN.NS", "SUNPHARMA.NS", "NESTLEIND.NS",
    "ULTRACEMCO.NS", "TATAMOTORS.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS",
    "HAL.NS", "IRFC.NS", "BEL.NS", "ADANIPORTS.NS", "TATASTEEL.NS",
]

# ---------------------------------------------------------------------------
# News feeds: (url, category)
# Categories: market, political, geopolitical, tech, ipo, defence, policy
# ---------------------------------------------------------------------------
NEWS_FEEDS = [
    # Economic Times — markets, companies, economy
    ("https://economictimes.indiatimes.com/rss.cms", "market"),
    ("https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "market"),
    ("https://economictimes.indiatimes.com/markets/stocks/news/rssfeeds/2146842.cms", "market"),
    ("https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms", "market"),
    ("https://economictimes.indiatimes.com/ipo/rssfeeds/125432745.cms", "ipo"),
    ("https://economictimes.indiatimes.com/news/politics-and-nation/rssfeeds/4393884.cms", "political"),
    ("https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms", "tech"),
    ("https://economictimes.indiatimes.com/news/defence/rssfeeds/1583776807.cms", "defence"),

    # Moneycontrol
    ("https://www.moneycontrol.com/rss/latestnews.xml", "market"),
    ("https://www.moneycontrol.com/rss/marketoutlook.xml", "market"),
    ("https://www.moneycontrol.com/rss/results.xml", "market"),

    # LiveMint
    ("https://www.livemint.com/rss/markets", "market"),
    ("https://www.livemint.com/rss/economy_politics", "political"),
    ("https://www.livemint.com/rss/companies", "market"),
    ("https://www.livemint.com/rss/technology", "tech"),

    # Business Standard
    ("https://www.business-standard.com/rss/markets-106.rss", "market"),
    ("https://www.business-standard.com/rss/economy-policy-102.rss", "policy"),
    ("https://www.business-standard.com/rss/companies-101.rss", "market"),
    ("https://www.business-standard.com/rss/finance-103.rss", "market"),

    # The Hindu Business Line
    ("https://www.thehindubusinessline.com/markets/rss?id=markets", "market"),
    ("https://www.thehindubusinessline.com/economy/rss?id=economy", "market"),

    # BBC — geopolitical
    ("https://feeds.bbci.co.uk/news/world/rss.xml", "geopolitical"),
    ("https://feeds.bbci.co.uk/news/business/rss.xml", "market"),
]

# Legacy: flat list for backward compat (used by scheduler)
NEWS_RSS_FEEDS = [url for url, _ in NEWS_FEEDS]
IPO_RSS_FEEDS = []  # Merged into NEWS_FEEDS

# ---------------------------------------------------------------------------
# Nifty 50 + key mid-caps for gainers/losers/market data
# ---------------------------------------------------------------------------
NIFTY_50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS",
    "HINDUNILVR.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "WIPRO.NS",
    "HCLTECH.NS", "BAJFINANCE.NS", "TITAN.NS", "SUNPHARMA.NS", "NESTLEIND.NS",
    "ULTRACEMCO.NS", "TATAMOTORS.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS",
    "TATASTEEL.NS", "INDUSINDBK.NS", "TECHM.NS", "BRITANNIA.NS", "DIVISLAB.NS",
    "CIPLA.NS", "GRASIM.NS", "APOLLOHOSP.NS", "ADANIPORTS.NS", "HEROMOTOCO.NS",
    "COALINDIA.NS", "EICHERMOT.NS", "DRREDDY.NS", "MOTHERSON.NS", "HDFCLIFE.NS",
    "BPCL.NS", "JSWSTEEL.NS", "LTIM.NS", "SBILIFE.NS", "ADANIENT.NS",
    # Key mid-caps: defence, railways, infra
    "HAL.NS", "BEL.NS", "BHEL.NS", "IRFC.NS", "RVNL.NS", "IRCTC.NS",
    "MAZDOCK.NS", "COCHINSHIP.NS", "GRSE.NS",
]


def to_yahoo_ticker(ticker: str) -> str:
    """Convert ticker to Yahoo Finance format. Adds .NS (NSE) if no exchange suffix."""
    t = ticker.upper().strip()
    if not t:
        return t
    if t.endswith(".NS") or t.endswith(".BO"):
        return t
    return f"{t}.NS"


def to_display_ticker(ticker: str) -> str:
    """Strip exchange suffix for display."""
    t = ticker.upper()
    for suffix in (".NS", ".BO"):
        if t.endswith(suffix):
            return t[: -len(suffix)]
    return t


# ---------------------------------------------------------------------------
# Scraper intervals (seconds)
# During market hours: faster refresh
# ---------------------------------------------------------------------------
NEWS_SCRAPE_INTERVAL = 10 * 60   # 10 minutes
STOCK_SCRAPE_INTERVAL = 5 * 60   # 5 minutes during market hours
PREDICTION_INTERVAL = 15 * 60    # 15 minutes for prediction pipeline

# API settings
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
