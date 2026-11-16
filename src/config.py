"""
Configuration, constants, and real-time stock search engine for TradeMind
"""
import difflib
import csv
import io
import re
from typing import Dict, List, Tuple
import requests

from src.settings import (
    DEFAULT_TARGETS,
    HTTP_TIMEOUT_SECONDS,
    NIFTY_50_CONSTITUENTS_URL,
    NIFTY_BANK_CONSTITUENTS_URL,
    SEARCH_RESULT_LIMIT,
    TIMEFRAME_OPTIONS,
    YAHOO_SEARCH_TIMEOUT_SECONDS,
)

# Comprehensive database of popular Indian equities across NSE
POPULAR_STOCKS: Dict[str, str] = {
    # Nifty 50 heavyweights
    "Reliance Industries": "RELIANCE.NS",
    "Tata Consultancy Services (TCS)": "TCS.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "Infosys": "INFY.NS",
    "State Bank of India (SBI)": "SBIN.NS",
    "Bharti Airtel": "BHARTIARTL.NS",
    "Larsen & Toubro (L&T)": "LT.NS",
    "ITC Limited": "ITC.NS",
    "Hindustan Unilever (HUL)": "HINDUNILVR.NS",
    "Bajaj Finance": "BAJFINANCE.NS",
    "Kotak Mahindra Bank": "KOTAKBANK.NS",
    "Axis Bank": "AXISBANK.NS",
    "Tata Motors": "TATAMOTORS.NS",
    "Sun Pharmaceutical": "SUNPHARMA.NS",
    "Titan Company": "TITAN.NS",
    "Maruti Suzuki": "MARUTI.NS",
    "NTPC": "NTPC.NS",
    "Power Grid Corporation": "POWERGRID.NS",
    "UltraTech Cement": "ULTRACEMCO.NS",
    "Oil and Natural Gas Corporation (ONGC)": "ONGC.NS",
    "Tata Steel": "TATASTEEL.NS",
    "Mahindra & Mahindra (M&M)": "M&M.NS",
    "Adani Enterprises": "ADANIENT.NS",
    "Adani Ports": "ADANIPORTS.NS",
    "Bajaj Finserv": "BAJAJFINSV.NS",
    "Coal India": "COALINDIA.NS",
    "Asian Paints": "ASIANPAINT.NS",
    "Bharat Petroleum (BPCL)": "BPCL.NS",
    "Grasim Industries": "GRASIM.NS",
    "Cipla": "CIPLA.NS",
    "Hero MotoCorp": "HEROMOTOCO.NS",
    "Hindalco Industries": "HINDALCO.NS",
    "JSW Steel": "JSWSTEEL.NS",
    "Tech Mahindra": "TECHM.NS",
    "Wipro": "WIPRO.NS",
    "Nestle India": "NESTLEIND.NS",
    "IndusInd Bank": "INDUSINDBK.NS",
    "Dr. Reddy's Laboratories": "DRREDDY.NS",
    "Apollo Hospitals": "APOLLOHOSP.NS",
    "Eicher Motors": "EICHERMOT.NS",
    "Divi's Laboratories": "DIVISLAB.NS",
    "Britannia Industries": "BRITANNIA.NS",
    "SBI Life Insurance": "SBILIFE.NS",
    "HDFC Life Insurance": "HDFCLIFE.NS",
    "Shriram Finance": "SHRIRAMFIN.NS",
    "Trent": "TRENT.NS",
    "Bharat Electronics (BEL)": "BEL.NS",
    
    # High-growth & popular momentum stocks
    "Zomato": "ZOMATO.NS",
    "Swiggy": "SWIGGY.NS",
    "Jio Financial Services": "JIOFIN.NS",
    "Tata Power": "TATAPOWER.NS",
    "Tata Technologies": "TATATECH.NS",
    "Tata Elxsi": "TATAELXSI.NS",
    "Suzlon Energy": "SUZLON.NS",
    "Hindustan Aeronautics (HAL)": "HAL.NS",
    "Indian Railway Finance Corporation (IRFC)": "IRFC.NS",
    "Indian Renewable Energy (IREDA)": "IREDA.NS",
    "Rail Vikas Nigam (RVNL)": "RVNL.NS",
    "Mazagon Dock Shipbuilders": "MAZDOCK.NS",
    "Bharat Heavy Electricals (BHEL)": "BHEL.NS",
    "Vedanta": "VEDL.NS",
    "Paytm (One97 Communications)": "PAYTM.NS",
    "Adani Power": "ADANIPOWER.NS",
    "Adani Green Energy": "ADANIGREEN.NS",
    "Reliance Power": "RPOWER.NS",
    "Reliance Infrastructure": "RELINFRA.NS",
    "Yes Bank": "YESBANK.NS",
    "Vodafone Idea": "IDEA.NS",
    "Punjab National Bank (PNB)": "PNB.NS",
    "Bank of Baroda": "BANKBARODA.NS",
    "Canara Bank": "CANBK.NS",
    "IDFC First Bank": "IDFCFIRSTB.NS",
    "Federal Bank": "FEDERALBNK.NS",
    "DLF Limited": "DLF.NS",
    "Godrej Properties": "GODREJPROP.NS",
    "Oberoi Realty": "OBEROIRLTY.NS",
    "Ashok Leyland": "ASHOKLEY.NS",
    "TVS Motor Company": "TVSMOTOR.NS",
    "Siemens India": "SIEMENS.NS",
    "ABB India": "ABB.NS",
    "Havells India": "HAVELLS.NS",
    "Polycab India": "POLYCAB.NS",
    "Dixon Technologies": "DIXON.NS",
    "KPIT Technologies": "KPITTECH.NS",
    "Persistent Systems": "PERSISTENT.NS",
    "Coforge": "COFORGE.NS",
    "LTIMindtree": "LTIM.NS",
    "Varun Beverages (VBL)": "VBL.NS",
    "Kalyan Jewellers": "KALYANKJIL.NS",
    "Nykaa (FSN E-Commerce)": "NYKAA.NS",
    "Delhivery": "DELHIVERY.NS",
    "PB Fintech (Policybazaar)": "POLICYBZR.NS",
    "CDSL": "CDSL.NS",
    "BSE Limited": "BSE.NS",
    "Angel One": "ANGELONE.NS",
    "REC Limited": "RECLTD.NS",
    "Power Finance Corporation (PFC)": "PFC.NS",
}

INDEX_CONSTITUENT_URLS = {
    "NIFTY 50": NIFTY_50_CONSTITUENTS_URL,
    "NIFTY BANK": NIFTY_BANK_CONSTITUENTS_URL,
}


def fetch_index_constituents(index_name: str) -> List[Dict[str, str]]:
    """Fetch the current constituent list from the official NSE Indices CSV."""
    url = INDEX_CONSTITUENT_URLS.get(index_name)
    if not url:
        return []

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "TradeMind/0.1"},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.content.decode("utf-8-sig")
        rows = []
        for row in csv.DictReader(io.StringIO(content)):
            symbol = (row.get("Symbol") or "").strip().upper()
            company_name = (row.get("Company Name") or "").strip()
            if not symbol or not company_name:
                continue
            rows.append(
                {
                    "name": company_name,
                    "symbol": f"{symbol}.NS",
                    "industry": (row.get("Industry") or "N/A").strip(),
                    "index": index_name,
                }
            )
        return rows
    except (requests.RequestException, UnicodeDecodeError, csv.Error, ValueError):
        return []


def _normalise_search_text(value: str) -> str:
    """Create a comparison-friendly representation for names and tickers."""
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _local_stock_matches(query: str, limit: int) -> List[Dict[str, str]]:
    """Return deterministic local matches before making a network request."""
    q_norm = _normalise_search_text(query)
    if not q_norm:
        return []

    scored = []
    for name, symbol in POPULAR_STOCKS.items():
        name_norm = _normalise_search_text(name)
        symbol_norm = _normalise_search_text(symbol.removesuffix(".NS").removesuffix(".BO"))

        if q_norm == symbol_norm or q_norm == name_norm:
            score = 1.0
        elif q_norm in name_norm or q_norm in symbol_norm:
            score = 0.9
        else:
            score = max(
                difflib.SequenceMatcher(None, q_norm, name_norm).ratio(),
                difflib.SequenceMatcher(None, q_norm, symbol_norm).ratio(),
            )

        # Short tickers have a high chance of accidental similarity (TCS vs
        # ITC/CDSL), so require a stronger fuzzy match for them.
        minimum_score = 0.7 if len(q_norm) <= 4 else 0.45
        if score >= minimum_score:
            scored.append((score, name, symbol))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"symbol": symbol, "name": name, "type": "Equity", "exchange": "NSE"}
        for _, name, symbol in scored[:limit]
    ]

def search_stocks(query: str, limit: int = SEARCH_RESULT_LIMIT) -> List[Dict[str, str]]:
    """
    Real-time intelligent stock search engine:
    1. Direct & substring matching on company names and symbols.
    2. Fuzzy matching (handles typos like 'Relieance', 'Tcs', 'Infi').
    3. Live Yahoo Finance search API query for Indian exchanges.
    Returns:
        List of dicts with 'symbol', 'name', 'type', and 'exchange'
    """
    clean_q = str(query or "").strip()
    if not clean_q:
        return []

    try:
        result_limit = max(1, min(int(limit), 20))
    except (TypeError, ValueError):
        result_limit = SEARCH_RESULT_LIMIT

    q_lower = clean_q.lower()
    q_upper = clean_q.upper()
    results: List[Dict[str, str]] = []
    seen_symbols = set()

    # 1. Check index keywords
    if "nifty" in q_lower:
        requested_index = next(
            (
                (name, symbol)
                for name, symbol in DEFAULT_TARGETS.items()
                if ("bank" in q_lower) == ("bank" in name.casefold())
            ),
            None,
        )
        if requested_index:
            index_name, index_symbol = requested_index
            results.append(
                {
                    "symbol": index_symbol,
                    "name": index_name.title(),
                    "type": "Index",
                    "exchange": "NSE",
                }
            )
            seen_symbols.add(index_symbol)

    # 2. Exact, substring, and fuzzy matches in the local database. Unlike the
    # old name-only fuzzy match, this also handles short tickers such as TCS.
    for item in _local_stock_matches(clean_q, result_limit):
        if item["symbol"] not in seen_symbols:
            results.append(item)
            seen_symbols.add(item["symbol"])

    # 3. Live Yahoo Finance Search API for real-time lookups. It is only used
    # when the local catalogue cannot fill the requested number of results.
    query_norm = _normalise_search_text(clean_q)
    has_exact_local_match = any(
        query_norm in {
            _normalise_search_text(name),
            _normalise_search_text(symbol.removesuffix(".NS").removesuffix(".BO")),
        }
        for name, symbol in POPULAR_STOCKS.items()
    )
    if len(results) < result_limit and not has_exact_local_match:
        try:
            url = "https://query2.finance.yahoo.com/v1/finance/search"
            resp = requests.get(
                url,
                params={"q": clean_q, "quotesCount": result_limit * 2, "newsCount": 0},
                headers={"User-Agent": "TradeMind/0.1"},
                timeout=YAHOO_SEARCH_TIMEOUT_SECONDS,
            )
            if resp.status_code == 200:
                data = resp.json()
                quotes = data.get("quotes", [])
                for item in quotes:
                    s = item.get("symbol", "")
                    # Prioritize Indian markets or clean matches
                    if s.endswith(".NS") or s.endswith(".BO") or item.get("exchange") in ("NSI", "BSE"):
                        if s not in seen_symbols:
                            company_name = item.get("shortname") or item.get("longname") or s
                            results.append({
                                "symbol": s,
                                "name": company_name,
                                "type": item.get("quoteType", "Equity"),
                                "exchange": "NSE" if s.endswith(".NS") else "BSE"
                            })
                            seen_symbols.add(s)
                            if len(results) >= result_limit:
                                break
        except (requests.RequestException, ValueError, TypeError):
            # Search still has a useful local catalogue when Yahoo is down.
            pass

    # 5. Fallback ticker generation if no matches at all
    if not results:
        fallback_sym = f"{q_upper}.NS" if not q_upper.endswith(".NS") and not q_upper.endswith(".BO") else q_upper
        results.append({"symbol": fallback_sym, "name": clean_q.title(), "type": "Equity", "exchange": "NSE"})

    return results[:result_limit]

def resolve_ticker(query: str) -> Tuple[str, str]:
    """
    Resolves query to the best matching symbol and display name using the search engine.
    """
    matches = search_stocks(query, limit=1)
    if matches:
        return matches[0]["symbol"], matches[0]["name"]
    clean_upper = query.strip().upper()
    return f"{clean_upper}.NS", query.strip().title()
