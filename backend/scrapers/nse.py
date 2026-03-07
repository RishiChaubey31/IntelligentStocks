"""
NSE India direct API integration.
Sources data straight from nseindia.com — no third-party intermediary.
Handles the session/cookie requirement NSE imposes on API calls.
"""
import logging
import time
import re
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

NSE_BASE = "https://www.nseindia.com"
BSE_BASE = "https://api.bseindia.com/BseIndiaAPI/api"

# Shared session — NSE requires visiting the homepage first to get cookies
_session: Optional[requests.Session] = None
_session_created: float = 0
_SESSION_TTL = 300  # Refresh session every 5 minutes


# Seed list of well-known NSE ETFs — used as fallback if live ETF API is unavailable
_KNOWN_ETFS: dict[str, str] = {
    "TATSILV":    "Tata Silver Exchange Traded Fund",
    "SILVERBEES": "Nippon India Silver ETF",
    "SILVERIETF": "ICICI Prudential Silver ETF",
    "GOLDBEES":   "Nippon India ETF Gold BeES",
    "GOLDIETF":   "ICICI Prudential Gold ETF",
    "TATGOLD":    "Tata Gold Exchange Traded Fund",
    "AXISGOLD":   "Axis Gold ETF",
    "HDFCGOLD":   "HDFC Gold Exchange Traded Fund",
    "NIFTYBEES":  "Nippon India ETF Nifty 50 BeES",
    "JUNIORBEES": "Nippon India ETF Nifty Next 50",
    "LIQUIDBEES": "Nippon India ETF Nifty 1D Rate Liquid BeES",
    "BANKBEES":   "Nippon India ETF Bank BeES",
    "ITBEES":     "Nippon India ETF Nifty IT",
    "PHARMABEES": "Mirae Asset Nifty India Pharma ETF",
    "INFRABEES":  "Nippon India ETF Nifty Infra BeES",
    "SHARIABEES": "Nippon India ETF Shariah BeES",
    "PSUBNKBEES": "Nippon India ETF Nifty PSU Bank BeES",
    "NETFIT":     "Nippon India ETF Nifty IT",
    "MOM100":     "Motilal Oswal Nifty Momentum 100 ETF",
    "QUAL30IETF": "ICICI Prudential Quality 30 ETF",
    "LOWVOLIETF": "ICICI Prudential Nifty Low Vol 30 ETF",
    "ALPHA":      "ICICI Prudential Alpha Low Vol 30 ETF",
    "MIDCAPETF":  "Mirae Asset Nifty Midcap 150 ETF",
    "SMALLCAP":   "Nippon India ETF Nifty Smallcap BeES",
    "NV20BEES":   "Nippon India ETF NV20",
    "CPSE":       "Nippon India ETF CPSE",
    "DIVOPPBEES": "Nippon India ETF Dividend Opportunities",
    "SENSEXBEES": "Mirae Asset BSE Sensex ETF",
    "HDFCNIFETF": "HDFC Nifty 50 ETF",
    "ICICIB22":   "ICICI Prudential Bharat 22 ETF",
    "BHARAT22ETF":"ICICI Prudential Bharat 22 ETF",
    "MOM50":      "Motilal Oswal Nifty 500 Momentum 50 ETF",
    "NETFNIF100": "Nippon India ETF Nifty 100",
    "NIFTY1GETF": "Nippon India ETF Nifty 1D Rate",
    "SETFNIFBK":  "SBI ETF Nifty Bank",
    "SETFNIF50":  "SBI ETF Nifty 50",
    "SETFNIF100": "SBI ETF BSE 100",
    "KOTAKNIFTY": "Kotak Nifty ETF",
    "KOTAKGOLD":  "Kotak Gold ETF",
    "KOTAKPSUBK": "Kotak Nifty PSU Bank ETF",
    "UTINIFTETF": "UTI Nifty 50 ETF",
    "AXISBPSETF": "Axis Nifty 100 Index Fund ETF",
    "TATANIFTY":  "Tata Nifty ETF",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}


def _get_session() -> requests.Session:
    """Return a session with valid NSE cookies, refreshing if stale."""
    global _session, _session_created
    now = time.time()
    if _session is None or (now - _session_created) > _SESSION_TTL:
        s = requests.Session()
        s.headers.update(_HEADERS)
        try:
            # Hit homepage to get cookies
            s.get(NSE_BASE, timeout=10)
            # Also hit market page to strengthen session
            s.get(f"{NSE_BASE}/market-data/live-equity-market", timeout=10)
        except Exception as e:
            logger.debug("NSE session init warning: %s", e)
        _session = s
        _session_created = now
    return _session


def _nse_get(path: str, params: dict | None = None, retries: int = 2) -> dict | list | None:
    """Make a GET request to NSE API."""
    for attempt in range(retries + 1):
        try:
            s = _get_session()
            resp = s.get(f"{NSE_BASE}{path}", params=params, timeout=12)
            if resp.status_code == 401 or resp.status_code == 403:
                # Force session refresh
                global _session_created
                _session_created = 0
                s = _get_session()
                resp = s.get(f"{NSE_BASE}{path}", params=params, timeout=12)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                logger.debug("NSE API error for %s: %s", path, e)
    return None


# ---------------------------------------------------------------------------
# Live quote
# ---------------------------------------------------------------------------

def get_nse_quote(symbol: str) -> dict | None:
    """
    Fetch live quote for an NSE equity/ETF symbol (without .NS suffix).
    Returns standardised dict or None on failure.
    """
    symbol = symbol.upper().replace(".NS", "").replace(".BO", "")
    data = _nse_get("/api/quote-equity", {"symbol": symbol})
    if not data:
        # Try ETF endpoint
        data = _nse_get("/api/quote-equity", {"symbol": symbol, "series": "EQ"})
    if not data:
        return None

    try:
        pd = data.get("priceInfo", {})
        info = data.get("info", {})
        metadata = data.get("metadata", {})

        ltp = pd.get("lastPrice") or pd.get("ltp")
        prev_close = pd.get("previousClose") or pd.get("prevClose")
        change = pd.get("change", 0)
        pct_change = pd.get("pChange", 0)

        return {
            "symbol": symbol,
            "ticker": f"{symbol}.NS",
            "company_name": info.get("companyName") or metadata.get("companyName", symbol),
            "series": metadata.get("series", "EQ"),
            "isin": info.get("isin") or metadata.get("isin", ""),
            "last_price": float(ltp) if ltp is not None else None,
            "prev_close": float(prev_close) if prev_close is not None else None,
            "change": float(change),
            "pct_change": float(pct_change),
            "open": float(pd.get("open", 0) or 0),
            "high": float(pd.get("intraDayHighLow", {}).get("max") or pd.get("dayHigh", 0) or 0),
            "low": float(pd.get("intraDayHighLow", {}).get("min") or pd.get("dayLow", 0) or 0),
            "week52_high": float(pd.get("weekHighLow", {}).get("max") or 0),
            "week52_low": float(pd.get("weekHighLow", {}).get("min") or 0),
            "volume": int(data.get("preOpenMarket", {}).get("totalTradedVolume") or 0),
            "market_cap": None,
            "source": "NSE India",
        }
    except Exception as e:
        logger.debug("NSE quote parse error for %s: %s", symbol, e)
        return None


# ---------------------------------------------------------------------------
# Stock search — ALL listed NSE securities
# ---------------------------------------------------------------------------

def search_nse(query: str, limit: int = 15) -> list[dict]:
    """
    Search ALL NSE-listed securities (equities + ETFs + SME) by name or symbol.
    Uses the locally cached master list as primary source (fast, comprehensive).
    Falls back to NSE autocomplete API for anything not in master.
    """
    if not query or len(query) < 1:
        return []

    # Primary: local master list (2,500+ symbols including all ETFs)
    results = _search_equities_master(query, limit)

    # Supplement with NSE autocomplete for any additional hits
    if len(results) < limit:
        try:
            data = _nse_get("/api/search-autocomplete", {"q": query}, retries=1)
            if data and isinstance(data, dict):
                existing_syms = {r["symbol"] for r in results}
                for item in data.get("symbols", []):
                    sym = item.get("symbol", "")
                    if sym and sym not in existing_syms:
                        results.append({
                            "symbol": sym,
                            "ticker": f"{sym}.NS",
                            "name": item.get("symbol_info") or item.get("company_name") or sym,
                            "series": item.get("series", "EQ"),
                            "exchange": "NSE",
                        })
                        existing_syms.add(sym)
                        if len(results) >= limit:
                            break
        except Exception:
            pass

    return results[:limit]


def _search_equities_master(query: str, limit: int = 15) -> list[dict]:
    """
    Search the in-memory equity master for matches.
    Priority: exact symbol match > symbol starts with > symbol contains > name contains.
    """
    master = _get_equity_master()
    if not master:
        return []

    q = query.upper().strip()
    exact, starts, sym_contains, name_contains = [], [], [], []

    for item in master:
        sym  = item.get("symbol", "").upper()
        name = item.get("name", "").upper()
        entry = {
            "symbol": item["symbol"],
            "ticker": f"{item['symbol']}.NS",
            "name": item.get("name", item["symbol"]),
            "series": item.get("series", "EQ"),
            "exchange": "NSE",
        }
        if sym == q:
            exact.append(entry)
        elif sym.startswith(q):
            starts.append(entry)
        elif q in sym:
            sym_contains.append(entry)
        elif q in name:
            name_contains.append(entry)

    combined = exact + starts + sym_contains + name_contains
    return combined[:limit]


# ---------------------------------------------------------------------------
# NSE equity master list (all listed securities)
# ---------------------------------------------------------------------------

_equity_master_cache: list[dict] = []
_equity_master_fetched: float = 0
_MASTER_TTL = 6 * 3600  # Refresh every 6 hours


def _get_equity_master() -> list[dict]:
    """
    Fetch and cache all NSE listed securities: equities + ETFs + SME + bonds.
    Covers ~2,500+ symbols from two NSE sources.
    """
    global _equity_master_cache, _equity_master_fetched
    now = time.time()
    if _equity_master_cache and (now - _equity_master_fetched) < _MASTER_TTL:
        return _equity_master_cache

    records: dict[str, dict] = {}  # keyed by symbol to avoid duplicates

    # ---- Source 1: ETF API (~316 ETFs: TATSILV, GOLDBEES, NIFTYBEES, etc.) ----
    # Try up to 3 times with increasing delays
    etf_loaded = False
    for attempt in range(3):
        try:
            nse_session = requests.Session()
            nse_session.headers.update(_HEADERS)
            nse_session.get(NSE_BASE, timeout=10)
            time.sleep(2 + attempt)  # 2s, 3s, 4s delays
            resp = nse_session.get(f"{NSE_BASE}/api/etf", timeout=15)
            if resp.status_code == 200 and resp.content and len(resp.content) > 100:
                data = resp.json()
                etf_list = data.get("data", []) if isinstance(data, dict) else data
                for item in etf_list:
                    sym  = item.get("symbol", "")
                    meta = item.get("meta", {})
                    name = meta.get("companyName") or item.get("assets") or sym
                    if sym:
                        records[sym] = {"symbol": sym, "name": name, "series": "ETF"}
                logger.info("NSE ETF list loaded: %d ETFs (attempt %d)", len(etf_list), attempt + 1)
                etf_loaded = True
                break
        except Exception as e:
            logger.debug("ETF fetch attempt %d failed: %s", attempt + 1, e)
            time.sleep(2)

    # ---- Fallback: seed well-known ETFs so search always works ----
    if not etf_loaded:
        logger.info("Using hardcoded ETF seed list as fallback")
        for sym, name in _KNOWN_ETFS.items():
            if sym not in records:
                records[sym] = {"symbol": sym, "name": name, "series": "ETF"}

    # ---- Source 2: Equity CSV (regular stocks ~2,249) ----
    try:
        resp = requests.get(
            "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
            headers={**_HEADERS, "Accept": "text/csv,*/*"},
            timeout=20,
        )
        if resp.status_code == 200:
            lines = resp.text.strip().splitlines()
            header = [h.strip().upper() for h in lines[0].split(",")]
            sym_idx  = next((i for i, h in enumerate(header) if h == "SYMBOL"), 0)
            name_idx = next((i for i, h in enumerate(header) if "NAME" in h or "COMPANY" in h), 1)
            ser_idx  = next((i for i, h in enumerate(header) if "SERIES" in h), 2)
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) > max(sym_idx, name_idx):
                    sym  = parts[sym_idx].strip().strip('"')
                    name = parts[name_idx].strip().strip('"')
                    ser  = parts[ser_idx].strip().strip('"') if ser_idx >= 0 and len(parts) > ser_idx else "EQ"
                    if sym and sym not in records:  # don't overwrite ETFs
                        records[sym] = {"symbol": sym, "name": name, "series": ser}
    except Exception as e:
        logger.debug("Equity CSV fetch error: %s", e)

    result = list(records.values())
    if result:
        _equity_master_cache = result
        _equity_master_fetched = now
        logger.info("NSE master loaded: %d symbols (equities + ETFs)", len(result))

    return _equity_master_cache


# ---------------------------------------------------------------------------
# Market movers from NSE directly
# ---------------------------------------------------------------------------

def get_nse_gainers_losers(limit: int = 10) -> dict:
    """Fetch top gainers and losers directly from NSE."""
    result = {"gainers": [], "losers": [], "most_active": []}
    try:
        data = _nse_get("/api/live-analysis-variations", {"index": "allSecurities"})
        if not data:
            data = _nse_get("/api/live-analysis-gainers-losers")
        if not data:
            return result

        def _fmt(item: dict) -> dict:
            return {
                "symbol": item.get("symbol", ""),
                "ticker": f"{item.get('symbol', '')}.NS",
                "company_name": item.get("companyName") or item.get("meta", {}).get("companyName", ""),
                "last_price": float(item.get("ltp") or item.get("lastPrice") or 0),
                "change_pct": float(item.get("perChange") or item.get("pChange") or 0),
                "source": "NSE India",
            }

        gainers = data.get("advances", data.get("gainers", []))[:limit]
        losers = data.get("declines", data.get("losers", []))[:limit]
        result["gainers"] = [_fmt(i) for i in gainers]
        result["losers"] = [_fmt(i) for i in losers]
    except Exception as e:
        logger.debug("NSE gainers/losers error: %s", e)
    return result


# ---------------------------------------------------------------------------
# Preload equity master in background
# ---------------------------------------------------------------------------

def preload_equity_master() -> int:
    """Preload equity master list. Call on startup."""
    records = _get_equity_master()
    return len(records)
