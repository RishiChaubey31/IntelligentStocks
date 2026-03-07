"""RSS news scraper for business/finance sources."""
import logging
from datetime import datetime
from urllib.parse import urlparse

import feedparser
import requests
from sqlalchemy.orm import Session

from backend.config import NEWS_FEEDS
from backend.db.models import News

logger = logging.getLogger(__name__)

SOURCE_NAMES = {
    "economictimes.indiatimes.com": "Economic Times",
    "moneycontrol.com": "Moneycontrol",
    "livemint.com": "LiveMint",
    "business-standard.com": "Business Standard",
    "indiatimes.com": "Economic Times",
    "thehindubusinessline.com": "Hindu Business Line",
    "bbci.co.uk": "BBC",
    "bbc.co.uk": "BBC",
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
}


def _get_source_name(url: str) -> str:
    """Extract source name from feed URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    for key, name in SOURCE_NAMES.items():
        if key in domain:
            return name
    return domain


def _parse_date(entry) -> datetime:
    """Parse publication date from feed entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime(*parsed[:6])
            except (TypeError, ValueError):
                pass
    return datetime.utcnow()


def fetch_and_store_news(db: Session) -> int:
    """
    Fetch news from all RSS feeds and store in database.
    Returns number of new articles stored.
    """
    from backend.intelligence.entity_extractor import extract_entities
    from backend.intelligence.event_classifier import classify_event

    count = 0
    for feed_url, category in NEWS_FEEDS:
        try:
            response = requests.get(feed_url, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            source = _get_source_name(feed_url)

            for entry in feed.entries[:25]:
                link = entry.get("link", "")
                if not link:
                    continue

                existing = db.query(News).filter(News.link == link).first()
                if existing:
                    continue

                published = _parse_date(entry)
                title = entry.get("title", "")[:512]
                summary = entry.get("summary", "")[:2000] if entry.get("summary") else None

                # Classify event and extract entities at ingest time
                event = classify_event(title, summary or "")
                tickers = extract_entities(f"{title} {summary or ''}")

                # Override category if event classification is more specific
                effective_category = category
                if event.event_type.value in ("govt_contract", "defence_order"):
                    effective_category = "market"
                elif event.event_type.value in ("ipo",):
                    effective_category = "ipo"

                news = News(
                    title=title,
                    link=link,
                    source=source,
                    category=effective_category,
                    published_at=published,
                    summary=summary,
                    tickers=",".join(tickers) if tickers else None,
                )
                db.add(news)
                count += 1

        except Exception as e:
            logger.warning("Failed to fetch feed %s: %s", feed_url, e)

    db.commit()
    return count
