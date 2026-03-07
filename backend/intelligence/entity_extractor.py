"""
Entity extraction: map company names/keywords in news headlines to NSE tickers.
Covers Nifty 500 + key mid-cap stocks.
"""
import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# COMPANY → NSE TICKER mapping (Yahoo Finance .NS format)
# Keys: all lowercase aliases/keywords  →  Value: NSE ticker without suffix
# ---------------------------------------------------------------------------
_RAW_MAP: dict[str, str] = {
    # --- Large Cap / Nifty 50 ---
    "reliance": "RELIANCE", "ril": "RELIANCE", "reliance industries": "RELIANCE",
    "tcs": "TCS", "tata consultancy": "TCS", "tata consultancy services": "TCS",
    "hdfc bank": "HDFCBANK", "hdfcbank": "HDFCBANK", "hdfc": "HDFCBANK",
    "infosys": "INFY", "infy": "INFY",
    "icici bank": "ICICIBANK", "icicibank": "ICICIBANK", "icici": "ICICIBANK",
    "sbi": "SBIN", "state bank": "SBIN", "state bank of india": "SBIN",
    "bharti airtel": "BHARTIARTL", "airtel": "BHARTIARTL", "bhartiartl": "BHARTIARTL",
    "itc": "ITC", "itc limited": "ITC",
    "kotak mahindra": "KOTAKBANK", "kotak bank": "KOTAKBANK", "kotakbank": "KOTAKBANK",
    "l&t": "LT", "larsen": "LT", "larsen & toubro": "LT", "larsen toubro": "LT",
    "hindustan unilever": "HINDUNILVR", "hul": "HINDUNILVR", "unilever india": "HINDUNILVR",
    "axis bank": "AXISBANK", "axisbank": "AXISBANK",
    "asian paints": "ASIANPAINT", "asianpaint": "ASIANPAINT",
    "maruti": "MARUTI", "maruti suzuki": "MARUTI",
    "wipro": "WIPRO",
    "hcl tech": "HCLTECH", "hcltech": "HCLTECH", "hcl technologies": "HCLTECH",
    "bajaj finance": "BAJFINANCE", "bajfinance": "BAJFINANCE",
    "titan": "TITAN", "titan company": "TITAN",
    "sun pharma": "SUNPHARMA", "sunpharma": "SUNPHARMA", "sun pharmaceutical": "SUNPHARMA",
    "nestle india": "NESTLEIND", "nestleind": "NESTLEIND", "nestle": "NESTLEIND",
    "ultratech cement": "ULTRACEMCO", "ultracemco": "ULTRACEMCO", "ultratech": "ULTRACEMCO",
    "tata motors": "TATAMOTORS", "tatamotors": "TATAMOTORS",
    "power grid": "POWERGRID", "powergrid": "POWERGRID", "power grid corporation": "POWERGRID",
    "ntpc": "NTPC", "ntpc limited": "NTPC",
    "ongc": "ONGC", "oil and natural gas": "ONGC",
    "tata steel": "TATASTEEL", "tatasteel": "TATASTEEL",
    "indusind bank": "INDUSINDBK", "indusindbk": "INDUSINDBK",
    "tech mahindra": "TECHM", "techm": "TECHM",
    "britannia": "BRITANNIA", "britannia industries": "BRITANNIA",
    "divis lab": "DIVISLAB", "divislab": "DIVISLAB", "divi's laboratories": "DIVISLAB",
    "cipla": "CIPLA",
    "grasim": "GRASIM", "grasim industries": "GRASIM",
    "apollo hospitals": "APOLLOHOSP", "apollohosp": "APOLLOHOSP", "apollo hospital": "APOLLOHOSP",
    "adani ports": "ADANIPORTS", "adaniports": "ADANIPORTS",
    "hero motocorp": "HEROMOTOCO", "heromotoco": "HEROMOTOCO", "hero honda": "HEROMOTOCO",
    "coal india": "COALINDIA", "coalindia": "COALINDIA",
    "eicher motors": "EICHERMOT", "eichermot": "EICHERMOT", "royal enfield": "EICHERMOT",
    "dr reddy": "DRREDDY", "drreddy": "DRREDDY", "dr reddy's": "DRREDDY",
    "hdfc life": "HDFCLIFE", "hdfclife": "HDFCLIFE",
    "bpcl": "BPCL", "bharat petroleum": "BPCL",
    "jsw steel": "JSWSTEEL", "jswsteel": "JSWSTEEL",
    "ltim": "LTIM", "lt infotech": "LTIM", "l&t technology": "LTIM", "ltimindtree": "LTIM",
    "sbi life": "SBILIFE", "sbilife": "SBILIFE", "sbi life insurance": "SBILIFE",
    "adani enterprises": "ADANIENT", "adanient": "ADANIENT",
    "bajaj finserv": "BAJAJFINSV", "bajajfinsv": "BAJAJFINSV",
    "bajaj auto": "BAJAJ-AUTO", "bajaj auto limited": "BAJAJ-AUTO",
    "m&m": "M&M", "mahindra": "M&M", "mahindra & mahindra": "M&M",
    "hindalco": "HINDALCO", "hindalco industries": "HINDALCO",
    "upl": "UPL", "upl limited": "UPL",
    "shree cement": "SHREECEM", "shreecem": "SHREECEM",
    "dmart": "DMART", "avenue supermarts": "DMART",
    "zomato": "ZOMATO",
    "paytm": "PAYTM", "one97 communications": "PAYTM",
    "nykaa": "NYKAA", "fss nykaa": "NYKAA",
    "policy bazaar": "POLICYBZR", "policybzr": "POLICYBZR",
    "freshworks": "FRESH",

    # --- Railways / Infrastructure ---
    "irfc": "IRFC", "indian railway finance": "IRFC", "indian railway finance corporation": "IRFC",
    "rvnl": "RVNL", "rail vikas nigam": "RVNL",
    "irctc": "IRCTC", "indian railway catering": "IRCTC",
    "ircon": "IRCON", "ircon international": "IRCON",
    "rites": "RITES", "rites limited": "RITES",
    "rail vikas": "RVNL",

    # --- Defence / Aerospace ---
    "hal": "HAL", "hindustan aeronautics": "HAL",
    "bel": "BEL", "bharat electronics": "BEL",
    "bhel": "BHEL", "bharat heavy electricals": "BHEL",
    "drdo": "BEL",  # DRDO often affects BEL
    "mazagon dock": "MAZDOCK", "mazdock": "MAZDOCK",
    "garden reach": "GRSE", "grse": "GRSE",
    "cochin shipyard": "COCHINSHIP", "cochinship": "COCHINSHIP",
    "bharat forge": "BHARATFORG", "bharatforg": "BHARATFORG",
    "data patterns": "DATAPATTNS",
    "solar industries": "SOLARINDS",

    # --- PSU / Energy ---
    "ioc": "IOC", "indian oil": "IOC",
    "hpcl": "HPCL", "hindustan petroleum": "HPCL",
    "gail": "GAIL", "gail india": "GAIL",
    "oil india": "OIL",
    "nhpc": "NHPC",
    "sjvn": "SJVN",
    "abb india": "ABB", "abb": "ABB",
    "siemens india": "SIEMENS",

    # --- Banking / Finance ---
    "bank of baroda": "BANKBARODA", "bankbaroda": "BANKBARODA", "bob": "BANKBARODA",
    "punjab national bank": "PNB", "pnb": "PNB",
    "canara bank": "CANBK",
    "union bank": "UNIONBANK",
    "idbi bank": "IDBI",
    "federal bank": "FEDERALBNK",
    "yes bank": "YESBANK",
    "idfc first": "IDFCFIRSTB",
    "bandhan bank": "BANDHANBNK",
    "rbl bank": "RBLBANK",
    "lic": "LICI", "life insurance corporation": "LICI",
    "general insurance": "GICRE",
    "new india assurance": "NIACL",
    "pfc": "PFC", "power finance": "PFC",
    "rec limited": "RECLTD", "rec": "RECLTD",
    "muthoot": "MUTHOOTFIN",
    "bajaj holdings": "BAJAJHLDNG",
    "cholamandalam": "CHOLAFIN",

    # --- IT / Technology ---
    "mphasis": "MPHASIS",
    "persistent systems": "PERSISTENT",
    "coforge": "COFORGE",
    "hexaware": "HEXAWARE",
    "cyient": "CYIENT",
    "mastek": "MASTEK",
    "kpit tech": "KPITTECH",
    "tata elxsi": "TATAELXSI",
    "zensar": "ZENSARTECH",
    "birlasoft": "BSOFT",
    "happiest minds": "HAPPSTMNDS",
    "indiamart": "INDIAMART",
    "just dial": "JUSTDIAL",
    "info edge": "NAUKRI", "naukri": "NAUKRI",
    "mapmyindia": "MAPMYINDIA",
    "nazara": "NAZARA",

    # --- Pharma / Healthcare ---
    "lupin": "LUPIN",
    "aurobindo": "AUROPHARMA",
    "torrent pharma": "TORNTPHARM",
    "alkem": "ALKEM",
    "ipca labs": "IPCA",
    "pfizer india": "PFIZER",
    "abbott india": "ABBOTINDIA",
    "sanofi india": "SANOFI",
    "max healthcare": "MAXHEALTH",
    "fortis": "FORTIS",
    "narayana hrudayalaya": "NH",
    "aster dm": "ASTERDM",
    "vijaya diagnostic": "VIJAYA",
    "metropolis": "METROPOLIS",
    "thyrocare": "THYROCARE",
    "suven pharma": "SUVENPHAR",

    # --- Auto / EV ---
    "tvs motor": "TVSMOTOR",
    "tata power": "TATAPOWER",
    "olectra": "OLECTRA",
    "ola electric": "OLAELEC",
    "exide": "EXIDEIND",
    "amara raja": "AMARAJABAT",
    "motherson": "MOTHERSON", "samvardhana motherson": "MOTHERSON",
    "bosch india": "BOSCHLTD",
    "minda industries": "MINDAIND",
    "endurance": "ENDURANCE",
    "schaeffler india": "SCHAEFFLER",
    "escorts": "ESCORTS", "escorts kubota": "ESCORTS",

    # --- FMCG / Consumer ---
    "godrej consumer": "GODREJCP",
    "godrej industries": "GODREJIND",
    "dabur": "DABUR",
    "marico": "MARICO",
    "emami": "EMAMILTD",
    "colgate": "COLPAL",
    "procter gamble": "PGHH",
    "glaxosmithkline": "GLAXO",
    "tata consumer": "TATACONSUM",
    "mtr foods": "MTRL",
    "jyothy labs": "JYOTHYLAB",
    "vbl": "VBL", "varun beverages": "VBL",

    # --- Cement / Building ---
    "acc": "ACC", "acc cement": "ACC",
    "ambuja cement": "AMBUJACEM",
    "ramco cement": "RAMCOCEM",
    "dalmia bharat": "DALBHARAT",
    "jk cement": "JKCEMENT",
    "heidelberg cement": "HEIDELBERG",
    "astral": "ASTRAL", "astral poly": "ASTRAL",
    "supreme industries": "SUPREMEIND",
    "pidilite": "PIDILITIND",

    # --- Real Estate ---
    "dlf": "DLF",
    "godrej properties": "GODREJPROP",
    "prestige estates": "PRESTIGE",
    "brigade enterprises": "BRIGADE",
    "oberoi realty": "OBEROIRLTY",
    "sobha": "SOBHA",
    "macrotech": "LODHA", "lodha": "LODHA",
    "phoenix mills": "PHOENIXLTD",
    "embassy reit": "EMBASSY",

    # --- Telecom ---
    "vodafone idea": "IDEA", "vi telecom": "IDEA",
    "bharti hexacom": "BHARTIHEX",
    "sterlite tech": "STLTECH",
    "hfcl": "HFCL",
    "tata communications": "TATACOMM",
    "indus towers": "INDUSTOWER",

    # --- Commodities / Metals ---
    "nmdc": "NMDC",
    "vedanta": "VEDL",
    "moil": "MOIL",
    "national aluminium": "NATIONALUM",
    "sail": "SAIL", "steel authority": "SAIL",
    "welspun corp": "WELCORP",

    # --- Media / Entertainment ---
    "zee entertainment": "ZEEL", "zee": "ZEEL",
    "sun tv": "SUNTV",
    "pvr inox": "PVRINOX", "pvr": "PVRINOX",
    "inox leisure": "PVRINOX",
    "tips industries": "TIPS",
    "balaji telefilms": "BALAJITELE",

    # --- Logistics / Supply Chain ---
    "container corporation": "CONCOR",
    "blue dart": "BLUEDART",
    "delhivery": "DELHIVERY",
    "gati": "GATI",
    "allcargo": "ALLCARGO",
    "mahindra logistics": "MAHLOG",
    "tvs supply chain": "TVSSCS",

    # --- Aviation ---
    "indigo": "INDIGO", "interglobe aviation": "INDIGO",
    "spicejet": "SPICEJET",
    "air india": "AIRINDIA",

    # --- Hospitality ---
    "indian hotels": "INDHOTEL", "taj hotels": "INDHOTEL",
    "lemon tree": "LEMONTREE",
    "eih": "EIHOTEL", "oberoi hotel": "EIHOTEL",

    # --- Agri / Fertilizers ---
    "upl": "UPL",
    "coromandel international": "COROMANDEL",
    "chambal fertilisers": "CHAMBLFERT",
    "gnfc": "GNFC",
    "iffco tokio": "IFFCOTOKIO",
    "kaveri seed": "KSCL",
    "rallis india": "RALLIS",
    "pi industries": "PIIND",
    "bayer cropscience": "BAYERCROP",

    # --- Miscellaneous ---
    "dixon tech": "DIXON", "dixon technologies": "DIXON",
    "amber enterprises": "AMBER",
    "varroc engineering": "VARROC",
    "ceat": "CEATLTD",
    "mrf": "MRF",
    "apollo tyres": "APOLLOTYRE",
    "jk tyre": "JKTYRE",
    "balkrishna industries": "BALKRISIND", "bkt tyre": "BALKRISIND",
    "kec international": "KEC",
    "kalpataru power": "KPP",
    "thermax": "THERMAX",
    "cummins india": "CUMMINSIND",
    "kirloskar": "KKC",
    "voltas": "VOLTAS",
    "blue star": "BLUESTAR",
    "whirlpool india": "WHIRLPOOL",
    "havells": "HAVELLS",
    "polycab": "POLYCAB",
    "finolex cables": "FINCABLES",
    "crompton": "CROMPTON",
    "orient electric": "ORIENTELEC",
    "sula wines": "SULA",
    "united breweries": "UBL",
    "radico khaitan": "RADICO",
    "globus spirits": "GLOBUSSPR",
    "united spirits": "MCDOWELL-N",
    "gillette india": "GILLETTE",
    "page industries": "PAGEIND",
    "raymond": "RAYMOND",
    "arvind": "ARVIND",
    "trident": "TRIDENT",
    "welspun india": "WELSPUNIND",

    # --- Index keywords ---
    "nifty": "NIFTY",
    "sensex": "SENSEX",
    "nse": "NSE",
    "bse": "BSE",
    "sebi": "SEBI",
    "rbi": "RBI",
}

# Build lowercased lookup
COMPANY_TICKER: dict[str, str] = {k.lower(): v for k, v in _RAW_MAP.items()}

# Nifty 500 NSE base symbols (no suffix) for direct ticker matching
NIFTY500_SYMBOLS: set[str] = {v for v in COMPANY_TICKER.values() if v not in {"NIFTY", "SENSEX", "NSE", "BSE", "SEBI", "RBI"}}

# Sector → list of tickers
SECTOR_TICKERS: dict[str, list[str]] = {
    "banking": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK", "BANKBARODA", "PNB", "IDFCFIRSTB", "FEDERALBNK"],
    "it": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "MPHASIS", "PERSISTENT", "COFORGE"],
    "pharma": ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "LUPIN", "AUROPHARMA", "TORNTPHARM", "ALKEM"],
    "auto": ["MARUTI", "TATAMOTORS", "M&M", "HEROMOTOCO", "EICHERMOT", "TVSMOTOR", "BAJAJ-AUTO"],
    "infra": ["LT", "ADANIPORTS", "POWERGRID", "NTPC", "IRFC", "RVNL", "IRCON"],
    "railway": ["IRFC", "RVNL", "IRCTC", "IRCON", "RITES"],
    "defence": ["HAL", "BEL", "BHEL", "MAZDOCK", "GRSE", "BHARATFORG", "COCHINSHIP"],
    "energy": ["RELIANCE", "ONGC", "BPCL", "IOC", "HPCL", "GAIL", "COALINDIA", "TATAPOWER"],
    "fmcg": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "COLPAL", "GODREJCP"],
    "metal": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL", "NMDC"],
    "cement": ["ULTRACEMCO", "ACC", "AMBUJACEM", "SHREECEM", "DALBHARAT", "RAMCOCEM"],
    "realty": ["DLF", "GODREJPROP", "PRESTIGE", "BRIGADE", "LODHA", "OBEROIRLTY"],
    "telecom": ["BHARTIARTL", "IDEA", "INDUSTOWER", "TATACOMM"],
    "finance": ["BAJFINANCE", "BAJAJFINSV", "PFC", "RECLTD", "MUTHOOTFIN", "CHOLAFIN"],
    "nbfc": ["BAJFINANCE", "PFC", "RECLTD", "MUTHOOTFIN", "CHOLAFIN"],
    "psu": ["SBIN", "BANKBARODA", "PNB", "NTPC", "POWERGRID", "COALINDIA", "ONGC", "BPCL", "IOC", "BHEL", "HAL", "BEL"],
}

# Event keywords → which sectors are primarily affected
EVENT_SECTOR_MAP: dict[str, list[str]] = {
    "railway": ["railway", "rail"],
    "defence": ["defence", "defense", "military", "army", "navy", "airforce", "missile", "weapon"],
    "banking": ["banking", "bank", "rbi", "repo rate", "monetary policy", "credit policy"],
    "it": ["it sector", "technology sector", "software exports", "tech"],
    "pharma": ["pharma", "drug", "fda", "usfda", "pharmaceutical", "medicine"],
    "energy": ["oil", "gas", "petroleum", "energy", "crude", "opec"],
    "infra": ["infrastructure", "roads", "highway", "smart city", "urban development"],
    "psu": ["disinvestment", "privatisation", "privatization", "public sector"],
}


def extract_entities(text: str) -> list[str]:
    """
    Extract NSE ticker symbols from text (headline + summary).
    Returns list of base NSE symbols (without .NS/.BO suffix).
    """
    if not text:
        return []

    text_lower = text.lower()
    text_upper = text.upper()
    found: set[str] = set()

    # 1. Direct ticker pattern match (e.g. NSE:RELIANCE, $RELIANCE, RELIANCE.NS)
    ticker_patterns = [
        r"NSE:([A-Z&\-]+)",
        r"BSE:([A-Z&\-]+)",
        r"\$([A-Z]{2,10})",
        r"\b([A-Z]{2,12})\.NS\b",
        r"\b([A-Z]{2,12})\.BO\b",
    ]
    for pat in ticker_patterns:
        matches = re.findall(pat, text_upper)
        for m in matches:
            if m in NIFTY500_SYMBOLS:
                found.add(m)

    # 2. Company name matching (longest match first to avoid partial hits)
    sorted_keys = sorted(COMPANY_TICKER.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in ("nifty", "sensex", "nse", "bse", "sebi", "rbi"):
            continue
        if len(key) < 3:
            continue
        # Word-boundary check
        if re.search(r"\b" + re.escape(key) + r"\b", text_lower):
            ticker = COMPANY_TICKER[key]
            if ticker not in {"NIFTY", "SENSEX", "NSE", "BSE", "SEBI", "RBI"}:
                found.add(ticker)

    # 3. Exact symbol match (standalone word, 2-12 uppercase letters)
    words = re.findall(r"\b[A-Z]{2,12}\b", text_upper)
    for w in words:
        if w in NIFTY500_SYMBOLS:
            found.add(w)

    return list(found)[:15]


def extract_sectors(text: str) -> list[str]:
    """Identify sectors mentioned in text."""
    text_lower = text.lower()
    sectors = []
    for sector, keywords in EVENT_SECTOR_MAP.items():
        for kw in keywords:
            if kw in text_lower:
                sectors.append(sector)
                break
    return list(set(sectors))


def get_sector_tickers(sectors: list[str]) -> list[str]:
    """Get tickers associated with given sectors."""
    tickers: set[str] = set()
    for s in sectors:
        tickers.update(SECTOR_TICKERS.get(s, []))
    return list(tickers)
