"""
Prediction engine: generate buy/sell predictions with timing intelligence.
For each news event + stock, produce: direction, % range, confidence, timing window, reasoning.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.intelligence.entity_extractor import extract_entities, extract_sectors, get_sector_tickers
from backend.intelligence.event_classifier import classify_event, EventType, ImpactLevel
from backend.db.models import News, Prediction, MarketEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Action types shown in UI
# ---------------------------------------------------------------------------
ACTION_BUY_NOW = "BUY NOW"
ACTION_BUY_AT_OPEN = "BUY AT OPEN"
ACTION_WAIT = "WAIT"
ACTION_WATCH = "WATCH"
ACTION_AVOID = "AVOID"
ACTION_SELL = "SELL"
ACTION_SELL_AT_OPEN = "SELL AT OPEN"


@dataclass
class PredictionResult:
    ticker: str
    news_id: int
    event_type: str
    predicted_direction: str        # "up" | "down" | "neutral"
    predicted_pct_low: float
    predicted_pct_high: float
    confidence: float               # 0-100
    action: str                     # ACTION_* constant
    timing_window: str              # plain-English timing
    entry_time: str                 # e.g. "9:15–9:45 AM IST"
    stop_loss_pct: float            # % below entry to place stop-loss
    reasoning: str                  # plain English chain of logic
    sector_impact: list[str] = field(default_factory=list)
    affected_tickers: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rules: EventType → prediction parameters
# ---------------------------------------------------------------------------
_EVENT_RULES: dict[EventType, dict] = {
    EventType.GOVT_CONTRACT: {
        "direction": "up",
        "pct_low": 2.0, "pct_high": 6.0,
        "confidence_base": 75,
        "action": ACTION_BUY_AT_OPEN,
        "timing": "Gap-up expected at open. Best entry: 9:15–9:45 AM IST within first 30 minutes.",
        "entry_time": "9:15–9:45 AM IST",
        "stop_loss_pct": 2.5,
        "reasoning_template": "{company} awarded government contract/order. Infra/PSU stocks typically gap up 2–6% on such announcements. High retail buying expected at market open.",
    },
    EventType.DEFENCE_ORDER: {
        "direction": "up",
        "pct_low": 3.0, "pct_high": 8.0,
        "confidence_base": 78,
        "action": ACTION_BUY_AT_OPEN,
        "timing": "Defence stocks historically gap up 3–8% on order announcements. Enter at open (9:15–9:45 AM IST).",
        "entry_time": "9:15–9:45 AM IST",
        "stop_loss_pct": 3.0,
        "reasoning_template": "{company} received defence order. Defence sector stocks typically see strong institutional and retail buying on such news.",
    },
    EventType.FUNDING: {
        "direction": "up",
        "pct_low": 1.5, "pct_high": 5.0,
        "confidence_base": 65,
        "action": ACTION_BUY_AT_OPEN,
        "timing": "Funding news drives momentum buyers at open. Enter in first 30 min (9:15–9:45 AM IST) or wait for initial pullback.",
        "entry_time": "9:15–10:00 AM IST",
        "stop_loss_pct": 2.5,
        "reasoning_template": "{company} funding/QIP/stake announcement. Capital infusion signals growth outlook. Moderate buy opportunity.",
    },
    EventType.IPO: {
        "direction": "up",
        "pct_low": 5.0, "pct_high": 20.0,
        "confidence_base": 70,
        "action": ACTION_WATCH,
        "timing": "IPO listing. Watch grey market premium (GMP) for direction. Enter after initial volatility settles (10:30–11:30 AM IST).",
        "entry_time": "10:30–11:30 AM IST",
        "stop_loss_pct": 5.0,
        "reasoning_template": "{company} IPO listing. Strong GMP stocks can rally 15–30% on listing day. High volatility in first hour.",
    },
    EventType.EARNINGS_BEAT: {
        "direction": "up",
        "pct_low": 2.5, "pct_high": 8.0,
        "confidence_base": 72,
        "action": ACTION_BUY_AT_OPEN,
        "timing": "Strong earnings beat — gap-up at open. Best entry: 9:15–9:45 AM IST. Expect continued buying through the day.",
        "entry_time": "9:15–9:45 AM IST",
        "stop_loss_pct": 2.5,
        "reasoning_template": "{company} reported better-than-expected results. Earnings beats typically drive 3–8% upside on result day with strong follow-through.",
    },
    EventType.EARNINGS_MISS: {
        "direction": "down",
        "pct_low": -8.0, "pct_high": -3.0,
        "confidence_base": 72,
        "action": ACTION_SELL_AT_OPEN,
        "timing": "Earnings miss — gap-down at open. Sell/short at open (9:15–9:30 AM IST). Recovery likely only after 3–5 sessions.",
        "entry_time": "9:15–9:30 AM IST (exit)",
        "stop_loss_pct": 3.0,
        "reasoning_template": "{company} missed earnings estimates. Sell pressure expected at open. Avoid catching the falling knife — wait for stabilization before re-entry.",
    },
    EventType.EARNINGS_NEUTRAL: {
        "direction": "neutral",
        "pct_low": -2.0, "pct_high": 2.0,
        "confidence_base": 45,
        "action": ACTION_WATCH,
        "timing": "Neutral results — wait 1 hour for price discovery. Enter after direction confirmed (10:15–11:00 AM IST).",
        "entry_time": "10:15–11:00 AM IST",
        "stop_loss_pct": 1.5,
        "reasoning_template": "{company} results are in line with expectations. No strong directional bias — watch price action before taking position.",
    },
    EventType.RBI_DECISION: {
        "direction": "neutral",
        "pct_low": -2.0, "pct_high": 3.0,
        "confidence_base": 55,
        "action": ACTION_WAIT,
        "timing": "RBI policy decision — wait 1–2 hours for direction clarity. Market volatile during statement. Enter after 11 AM IST.",
        "entry_time": "11:00 AM–12:00 PM IST",
        "stop_loss_pct": 2.0,
        "reasoning_template": "RBI monetary policy decision announced. Banking stocks and rate-sensitives will be most impacted. Wait for initial reaction to settle before positioning.",
    },
    EventType.POLICY_CHANGE: {
        "direction": "neutral",
        "pct_low": -3.0, "pct_high": 4.0,
        "confidence_base": 55,
        "action": ACTION_WAIT,
        "timing": "Policy news — wait 1–2 hours for sector-specific impact to play out. Enter after 11 AM IST.",
        "entry_time": "11:00 AM–12:00 PM IST",
        "stop_loss_pct": 2.0,
        "reasoning_template": "{company} / sector affected by new government policy. Direction depends on policy specifics. Monitor sector leaders for confirmation.",
    },
    EventType.REGULATORY_ACTION: {
        "direction": "down",
        "pct_low": -10.0, "pct_high": -3.0,
        "confidence_base": 78,
        "action": ACTION_AVOID,
        "timing": "Regulatory action / ban — strong sell signal. Avoid at open. Wait for stabilization after 1–2 days.",
        "entry_time": "Avoid for 1–2 sessions",
        "stop_loss_pct": 5.0,
        "reasoning_template": "{company} faces regulatory action / investigation. Such events typically cause 5–15% decline. Avoid until regulatory clarity.",
    },
    EventType.MERGER_ACQUISITION: {
        "direction": "up",
        "pct_low": 3.0, "pct_high": 15.0,
        "confidence_base": 68,
        "action": ACTION_WATCH,
        "timing": "M&A news — target stock likely to gap up. Watch for deal details confirmation. Enter after initial reaction (10:00–11:00 AM IST).",
        "entry_time": "10:00–11:00 AM IST",
        "stop_loss_pct": 3.5,
        "reasoning_template": "{company} merger/acquisition announced. Target company typically trades at premium. Enter after deal validation.",
    },
    EventType.MANAGEMENT_CHANGE: {
        "direction": "down",
        "pct_low": -5.0, "pct_high": -1.0,
        "confidence_base": 55,
        "action": ACTION_WATCH,
        "timing": "Management change — initial sell-off likely. Wait 1 session for clarity. Enter only if fundamentals unchanged.",
        "entry_time": "Day+1, after 10:00 AM IST",
        "stop_loss_pct": 3.0,
        "reasoning_template": "{company} key management change announced. Market uncertainty typically drives initial decline. Wait for more details.",
    },
    EventType.GEOPOLITICAL: {
        "direction": "down",
        "pct_low": -5.0, "pct_high": -1.0,
        "confidence_base": 60,
        "action": ACTION_AVOID,
        "timing": "Geopolitical risk — broad market sell-off possible. Avoid new positions. Defensives (pharma, FMCG) may outperform.",
        "entry_time": "Wait for clarity",
        "stop_loss_pct": 3.0,
        "reasoning_template": "Geopolitical event detected. Broad market risk-off sentiment expected. Energy stocks may spike; financials likely to decline.",
    },
    EventType.MACRO_ECONOMIC: {
        "direction": "neutral",
        "pct_low": -2.0, "pct_high": 2.0,
        "confidence_base": 45,
        "action": ACTION_WATCH,
        "timing": "Macro data — sector-specific impact. Watch for 1 hour before positioning.",
        "entry_time": "10:30–11:30 AM IST",
        "stop_loss_pct": 2.0,
        "reasoning_template": "Macro economic data released. Impact varies by sector. Monitor index reaction before stock-specific positions.",
    },
    EventType.SECTOR_NEWS: {
        "direction": "neutral",
        "pct_low": -1.5, "pct_high": 2.5,
        "confidence_base": 40,
        "action": ACTION_WATCH,
        "timing": "Sector-level news — watch sector leaders for direction confirmation.",
        "entry_time": "10:30 AM–12:00 PM IST",
        "stop_loss_pct": 2.0,
        "reasoning_template": "Sector news detected. Monitor sector ETF (Nifty Bank / Nifty IT / Nifty Pharma) for direction before individual stock entry.",
    },
}

_DEFAULT_RULE = {
    "direction": "neutral",
    "pct_low": -1.0, "pct_high": 1.5,
    "confidence_base": 35,
    "action": ACTION_WATCH,
    "timing": "No strong directional signal. Monitor and wait for confirmation.",
    "entry_time": "N/A",
    "stop_loss_pct": 1.5,
    "reasoning_template": "General market news for {company}. No specific event pattern detected.",
}


def _sentiment_confidence_boost(sentiment_score: float | None) -> float:
    """Boost/reduce confidence based on VADER sentiment."""
    if sentiment_score is None:
        return 0
    if sentiment_score > 0.5:
        return 12
    if sentiment_score > 0.2:
        return 7
    if sentiment_score < -0.5:
        return 12
    if sentiment_score < -0.2:
        return 7
    return 3


def _build_reasoning(template: str, company: str, news_title: str, event_type: str,
                     sectors: list[str], additional_tickers: list[str]) -> str:
    """Build plain-English reasoning string."""
    reasoning = template.format(company=company)
    if sectors:
        reasoning += f" Sectors in focus: {', '.join(sectors[:3])}."
    if additional_tickers and len(additional_tickers) > 1:
        others = [t for t in additional_tickers[:5] if t != company]
        if others:
            reasoning += f" Related stocks to watch: {', '.join(others)}."
    return reasoning


def generate_prediction_for_news(
    news: News,
    ticker: str,
    company_name: str,
    sectors: list[str],
    all_affected_tickers: list[str],
) -> Optional[PredictionResult]:
    """Generate a single prediction for one ticker from one news item."""
    event = classify_event(news.title, news.summary or "")
    rule = _EVENT_RULES.get(event.event_type, _DEFAULT_RULE)

    if event.event_type == EventType.GENERAL and event.impact == ImpactLevel.LOW:
        return None

    confidence = rule["confidence_base"]
    confidence += _sentiment_confidence_boost(news.sentiment_score)

    if event.impact == ImpactLevel.HIGH:
        confidence = min(92, confidence + 5)
    elif event.impact == ImpactLevel.LOW:
        confidence = max(25, confidence - 10)

    confidence = round(min(95, max(20, confidence)), 1)

    reasoning = _build_reasoning(
        rule["reasoning_template"],
        company=company_name,
        news_title=news.title,
        event_type=event.event_type.value,
        sectors=sectors,
        additional_tickers=all_affected_tickers,
    )

    return PredictionResult(
        ticker=ticker,
        news_id=news.id,
        event_type=event.event_type.value,
        predicted_direction=rule["direction"],
        predicted_pct_low=rule["pct_low"],
        predicted_pct_high=rule["pct_high"],
        confidence=confidence,
        action=rule["action"],
        timing_window=rule["timing"],
        entry_time=rule["entry_time"],
        stop_loss_pct=rule["stop_loss_pct"],
        reasoning=reasoning,
        sector_impact=sectors,
        affected_tickers=all_affected_tickers,
    )


def generate_predictions(db: Session, news_items: list[News]) -> list[PredictionResult]:
    """
    Generate predictions from a list of news items.
    For each news item, extract entities and produce per-ticker predictions.
    """
    results: list[PredictionResult] = []
    seen: set[tuple[int, str]] = set()  # (news_id, ticker)

    for news in news_items:
        text = f"{news.title} {news.summary or ''}"

        # Extract direct company mentions
        direct_tickers = extract_entities(text)
        sectors = extract_sectors(text)
        sector_tickers = get_sector_tickers(sectors)

        # Combine: direct mentions first, then sector-correlated
        all_tickers = list(dict.fromkeys(direct_tickers + sector_tickers))

        if not all_tickers:
            continue

        for ticker in all_tickers[:10]:
            key = (news.id, ticker)
            if key in seen:
                continue
            seen.add(key)

            company_name = ticker
            pred = generate_prediction_for_news(
                news=news,
                ticker=ticker,
                company_name=company_name,
                sectors=sectors,
                all_affected_tickers=all_tickers[:8],
            )
            if pred:
                results.append(pred)

    return results


def run_prediction_pipeline(db: Session) -> int:
    """
    Full pipeline: fetch recent news → classify events → generate predictions → store in DB.
    Returns count of new predictions stored.
    """
    cutoff = datetime.utcnow() - timedelta(hours=24)
    news_items = db.query(News).filter(
        News.published_at >= cutoff,
        News.sentiment_score.isnot(None),
    ).order_by(News.published_at.desc()).limit(100).all()

    if not news_items:
        logger.info("No recent news for prediction pipeline.")
        return 0

    predictions = generate_predictions(db, news_items)

    # Store events and predictions
    count = 0
    for pred in predictions:
        # Check if prediction already exists for this news+ticker combo
        existing = db.query(Prediction).filter(
            Prediction.news_id == pred.news_id,
            Prediction.ticker == pred.ticker,
        ).first()
        if existing:
            continue

        db_pred = Prediction(
            ticker=pred.ticker,
            news_id=pred.news_id,
            event_type=pred.event_type,
            predicted_direction=pred.predicted_direction,
            predicted_pct_low=pred.predicted_pct_low,
            predicted_pct_high=pred.predicted_pct_high,
            confidence=pred.confidence,
            action=pred.action,
            timing_window=pred.timing_window,
            entry_time=pred.entry_time,
            stop_loss_pct=pred.stop_loss_pct,
            reasoning=pred.reasoning,
            sector_impact=",".join(pred.sector_impact) if pred.sector_impact else None,
            affected_tickers=",".join(pred.affected_tickers) if pred.affected_tickers else None,
        )
        db.add(db_pred)
        count += 1

    # Store market events (one per high-impact news)
    for news in news_items:
        existing_event = db.query(MarketEvent).filter(MarketEvent.news_id == news.id).first()
        if existing_event:
            continue

        event = classify_event(news.title, news.summary or "")
        if event.event_type == EventType.GENERAL:
            continue

        tickers = extract_entities(f"{news.title} {news.summary or ''}")
        sectors = extract_sectors(f"{news.title} {news.summary or ''}")

        db_event = MarketEvent(
            news_id=news.id,
            event_type=event.event_type.value,
            impact=event.impact.value,
            affected_tickers=",".join(tickers[:8]) if tickers else None,
            affected_sectors=",".join(sectors[:5]) if sectors else None,
            sentiment_hint=event.sentiment_hint,
            keywords=",".join(event.keywords_matched[:3]) if event.keywords_matched else None,
            title=news.title[:512],
            source=news.source,
            published_at=news.published_at,
        )
        db.add(db_event)

    db.commit()
    logger.info("Prediction pipeline: %d new predictions stored.", count)
    return count
