"""Scrapers module."""
from backend.scrapers.news import fetch_and_store_news
from backend.scrapers.stocks import fetch_and_store_stocks, get_watchlist_tickers
from backend.scrapers.market import fetch_gainers_losers_active

__all__ = [
    "fetch_and_store_news",
    "fetch_and_store_stocks",
    "get_watchlist_tickers",
    "fetch_gainers_losers_active",
]
