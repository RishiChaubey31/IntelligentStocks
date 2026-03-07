"""
Event classification: detect market-moving event types from news headlines.
Assigns event type, impact level, and affected sectors.
"""
import re
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    GOVT_CONTRACT = "govt_contract"
    DEFENCE_ORDER = "defence_order"
    FUNDING = "funding"
    IPO = "ipo"
    EARNINGS_BEAT = "earnings_beat"
    EARNINGS_MISS = "earnings_miss"
    EARNINGS_NEUTRAL = "earnings_neutral"
    POLICY_CHANGE = "policy_change"
    RBI_DECISION = "rbi_decision"
    REGULATORY_ACTION = "regulatory_action"
    MERGER_ACQUISITION = "merger_acquisition"
    MANAGEMENT_CHANGE = "management_change"
    GEOPOLITICAL = "geopolitical"
    MACRO_ECONOMIC = "macro_economic"
    SECTOR_NEWS = "sector_news"
    MARKET_NEWS = "market_news"
    GENERAL = "general"


class ImpactLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ClassifiedEvent:
    event_type: EventType
    impact: ImpactLevel
    affected_sectors: list[str] = field(default_factory=list)
    keywords_matched: list[str] = field(default_factory=list)
    sentiment_hint: str = "neutral"  # "positive", "negative", "neutral"


# ---------------------------------------------------------------------------
# Keyword → (EventType, ImpactLevel, sentiment_hint)
# Ordered from most specific to most general
# ---------------------------------------------------------------------------
_RULES: list[tuple[list[str], EventType, ImpactLevel, str]] = [
    # --- Government contracts ---
    (["awarded contract", "bags contract", "wins contract", "secures contract",
      "railway project", "defence contract", "government order", "ministry order",
      "ministry of railways", "ministry of defence", "national highway authority",
      "nhai order", "metro rail project", "smart city project", "pm gati shakti",
      "infrastructure project awarded", "l1 bidder", "wins bid", "bags order",
      "work order", "order worth", "order inflow", "order book", "bagged order",
      "receives order", "gets order", "wins order"],
     EventType.GOVT_CONTRACT, ImpactLevel.HIGH, "positive"),

    # --- Defence orders ---
    (["defence order", "defense order", "drdo", "indigenous missile", "hal delivers",
      "navy order", "army order", "air force order", "combat aircraft", "howitzer",
      "frigate", "submarine", "armoured vehicle", "defence export"],
     EventType.DEFENCE_ORDER, ImpactLevel.HIGH, "positive"),

    # --- Fundraising ---
    (["raises funds", "fund raise", "fundraise", "qip", "rights issue", "preferential allotment",
      "fpo", "ncd", "non-convertible debenture", "raises ₹", "raises rs",
      "investment round", "series a", "series b", "series c", "venture capital",
      "private equity", "stake sale"],
     EventType.FUNDING, ImpactLevel.MEDIUM, "positive"),

    # --- IPO ---
    (["ipo", "initial public offering", "listing debut", "grey market premium", "gmp",
      "ipo allotment", "ipo subscription", "ipo price band", "mainboard ipo", "sme ipo"],
     EventType.IPO, ImpactLevel.HIGH, "positive"),

    # --- Earnings beat ---
    (["profit jumps", "profit surges", "profit up", "profit rises", "net profit up",
      "beats estimates", "beats expectations", "better than expected", "earnings beat",
      "revenue surges", "revenue up", "revenue jumps", "ebitda rises", "ebitda up",
      "margins improve", "margin expansion", "record profit", "record revenue",
      "strong results", "bumper results", "stellar results",
      "q1 profit", "q2 profit", "q3 profit", "q4 profit"],
     EventType.EARNINGS_BEAT, ImpactLevel.HIGH, "positive"),

    # --- Earnings miss ---
    (["profit falls", "profit drops", "profit declines", "profit slumps", "profit contracts",
      "net loss", "loss widens", "misses estimates", "below expectations", "earnings miss",
      "revenue declines", "revenue falls", "ebitda falls", "margins contract",
      "margin compression", "weak results", "disappoints", "disappointing results",
      "q1 loss", "q2 loss", "q3 loss", "q4 loss"],
     EventType.EARNINGS_MISS, ImpactLevel.HIGH, "negative"),

    # --- Earnings neutral ---
    (["quarterly results", "q1 results", "q2 results", "q3 results", "q4 results",
      "annual results", "fy results", "financial results", "declares dividend"],
     EventType.EARNINGS_NEUTRAL, ImpactLevel.MEDIUM, "neutral"),

    # --- RBI decision ---
    (["rbi rate", "repo rate", "reverse repo", "monetary policy committee", "mpc meeting",
      "rbi policy", "rbi decision", "rate hike", "rate cut", "rate unchanged",
      "rbi governor", "liquidity infusion", "crr cut", "slr change"],
     EventType.RBI_DECISION, ImpactLevel.HIGH, "neutral"),

    # --- Policy changes ---
    (["sebi circular", "sebi regulation", "sebi order", "new policy", "government policy",
      "budget proposal", "tax relief", "gst cut", "gst hike", "import duty",
      "export ban", "production-linked incentive", "pli scheme", "subsidy",
      "disinvestment", "privatization", "nationalization"],
     EventType.POLICY_CHANGE, ImpactLevel.HIGH, "neutral"),

    # --- Regulatory action ---
    (["sebi ban", "show cause notice", "investigation", "cbi raid", "ed probe",
      "income tax raid", "rbi penalty", "fine imposed", "penalty", "fraud detected",
      "npa", "default", "debt restructuring", "ban on", "suspended", "delisted"],
     EventType.REGULATORY_ACTION, ImpactLevel.HIGH, "negative"),

    # --- M&A ---
    (["merger", "acquisition", "acquires", "takeover", "buyout", "amalgamation",
      "stake acquisition", "joint venture", "strategic alliance", "mou signed",
      "binding agreement", "deal signed", "buys stake"],
     EventType.MERGER_ACQUISITION, ImpactLevel.MEDIUM, "positive"),

    # --- Management change ---
    (["ceo resigns", "md resigns", "cfo leaves", "new ceo", "new md", "new cfo",
      "management change", "board reshuffle", "chairman steps down", "promoter sells"],
     EventType.MANAGEMENT_CHANGE, ImpactLevel.MEDIUM, "negative"),

    # --- Geopolitical ---
    (["war", "military conflict", "sanctions", "geopolitical tension", "border dispute",
      "ceasefire", "nuclear", "us-china", "russia", "israel", "iran", "crude oil spike",
      "oil price surge", "global recession", "trade war"],
     EventType.GEOPOLITICAL, ImpactLevel.HIGH, "negative"),

    # --- Macro ---
    (["gdp", "inflation", "cpi", "wpi", "iip", "trade deficit", "current account",
      "fiscal deficit", "foreign reserve", "rupee", "dollar index", "fed rate",
      "us fed", "federal reserve", "global cues"],
     EventType.MACRO_ECONOMIC, ImpactLevel.MEDIUM, "neutral"),

    # --- Sector news ---
    (["sector outlook", "sector report", "industry report", "it sector", "banking sector",
      "pharma sector", "auto sector", "fmcg sector", "nifty bank", "nifty it",
      "nifty pharma", "nifty auto"],
     EventType.SECTOR_NEWS, ImpactLevel.MEDIUM, "neutral"),

    # --- Market news ---
    (["nifty", "sensex", "market rally", "market crash", "stock market", "bull run",
      "bear market", "foreign institutional", "fii", "dii", "fpi inflow", "fpi outflow"],
     EventType.MARKET_NEWS, ImpactLevel.LOW, "neutral"),
]

# Sector keyword map for affected_sectors detection
_SECTOR_KEYWORDS: dict[str, list[str]] = {
    "railway": ["railway", "rail", "irfc", "rvnl", "irctc"],
    "defence": ["defence", "defense", "military", "drdo", "hal", "bel"],
    "banking": ["bank", "rbi", "nbfc", "credit", "lending", "npa"],
    "it": ["it ", "software", "tech", "digital", "cloud", "ai "],
    "pharma": ["pharma", "drug", "medicine", "hospital", "healthcare"],
    "energy": ["oil", "gas", "petroleum", "crude", "energy", "power"],
    "infra": ["infrastructure", "highway", "road", "bridge", "metro", "airport"],
    "auto": ["automobile", "car", "vehicle", "ev ", "electric vehicle"],
    "fmcg": ["fmcg", "consumer goods", "foods", "beverage"],
    "metal": ["steel", "aluminium", "copper", "metal", "mining"],
    "cement": ["cement"],
    "realty": ["real estate", "realty", "housing", "property"],
    "telecom": ["telecom", "spectrum", "5g", "broadband"],
    "finance": ["finance", "insurance", "mutual fund", "nbfc"],
}


def classify_event(title: str, summary: str = "") -> ClassifiedEvent:
    """
    Classify a news item into an EventType with impact level.
    Returns ClassifiedEvent with event_type, impact, affected_sectors, sentiment_hint.
    """
    text = f"{title} {summary or ''}".lower()

    matched_event = EventType.GENERAL
    matched_impact = ImpactLevel.LOW
    matched_sentiment = "neutral"
    matched_keywords: list[str] = []

    for keywords, event_type, impact, sentiment in _RULES:
        for kw in keywords:
            if kw in text:
                matched_event = event_type
                matched_impact = impact
                matched_sentiment = sentiment
                matched_keywords.append(kw)
                break
        if matched_keywords:
            break

    # Detect affected sectors
    affected = []
    for sector, kws in _SECTOR_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                affected.append(sector)
                break

    return ClassifiedEvent(
        event_type=matched_event,
        impact=matched_impact,
        affected_sectors=affected,
        keywords_matched=matched_keywords[:3],
        sentiment_hint=matched_sentiment,
    )


def get_impact_score(event: ClassifiedEvent) -> int:
    """Numeric impact score: high=3, medium=2, low=1."""
    return {"high": 3, "medium": 2, "low": 1}.get(event.impact.value, 1)
