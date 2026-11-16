"""Market-universe scanning for the TradeMind dashboard.

The scanner deliberately uses technical screening buckets instead of making a
Gemini request for every constituent. This keeps a one-click universe view
fast, repeatable, and inexpensive; users can open any row for full analysis.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from src.config import fetch_index_constituents
from src.data_fetcher import fetch_stock_data
from src.settings import (
    BUY_RSI_MAX,
    BUY_RSI_MIN,
    DEFAULT_PERIOD,
    DEFAULT_SCANNER_INDEXES,
    SCANNER_MAX_WORKERS,
    SELL_RSI_MIN,
)


def technical_bucket(metrics: Dict[str, Any]) -> str:
    """Classify a stock using trend alignment and RSI as a screening signal."""
    trend = metrics.get("trend_signal")
    rsi = metrics.get("rsi", metrics.get("rsi_14"))
    if trend == "Insufficient history" or not isinstance(rsi, (int, float)):
        return "WATCH"

    # These are screening labels, not personalised recommendations. Avoid
    # buying an extended trend and avoid treating an oversold bearish stock as
    # an automatic sell.
    if trend == "Bullish" and BUY_RSI_MIN <= rsi < BUY_RSI_MAX:
        return "BUY"
    if trend == "Bearish" and rsi > SELL_RSI_MIN:
        return "SELL"
    return "HOLD"


def _merge_constituents(index_names: Iterable[str]) -> List[Dict[str, Any]]:
    """Merge overlapping index memberships into unique ticker records."""
    by_symbol: Dict[str, Dict[str, Any]] = {}
    for index_name in index_names:
        for item in fetch_index_constituents(index_name):
            symbol = item["symbol"]
            if symbol not in by_symbol:
                by_symbol[symbol] = {
                    "name": item["name"],
                    "symbol": symbol,
                    "industry": item.get("industry", "N/A"),
                    "indexes": [],
                }
            if index_name not in by_symbol[symbol]["indexes"]:
                by_symbol[symbol]["indexes"].append(index_name)
    return sorted(by_symbol.values(), key=lambda item: item["name"])


def _scan_one(item: Dict[str, Any], period: str) -> Dict[str, Any]:
    result = fetch_stock_data(item["symbol"], period=period, include_info=False)
    base = {
        "company": item["name"],
        "symbol": item["symbol"],
        "industry": item["industry"],
        "index": ", ".join(item["indexes"]),
    }
    if result.get("error"):
        return {
            **base,
            "status": "Unavailable",
            "error": result["error"],
            "last_price": None,
            "day_change_pct": None,
            "rsi": None,
            "trend": "N/A",
            "bucket": "N/A",
        }

    metrics = result["metrics"]
    return {
        **base,
        "status": "OK",
        "error": None,
        "last_price": metrics.get("latest_close"),
        "day_change_pct": metrics.get("pct_change"),
        "rsi": metrics.get("rsi", metrics.get("rsi_14")),
        "trend": metrics.get("trend_signal"),
        "bucket": technical_bucket(metrics),
        "trend_detail": metrics.get("trend_signal_detail", ""),
        "data_as_of": result.get("data_as_of"),
    }


def scan_market_universe(
    period: str = DEFAULT_PERIOD,
    index_names: Iterable[str] = DEFAULT_SCANNER_INDEXES,
    max_workers: int = SCANNER_MAX_WORKERS,
) -> Dict[str, Any]:
    """Fetch a cached-friendly technical snapshot for the default universe."""
    constituents = _merge_constituents(index_names)
    if not constituents:
        return {
            "error": "Could not load current Nifty constituents from NSE Indices.",
            "rows": [],
            "counts": {},
        }

    rows: List[Dict[str, Any]] = []
    worker_count = max(1, min(int(max_workers), len(constituents)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(_scan_one, item, period) for item in constituents]
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as error:
                rows.append({"status": "Unavailable", "error": str(error)})

    rows.sort(key=lambda item: item.get("company", ""))
    counts = Counter(row.get("bucket", "N/A") for row in rows)
    return {
        "error": None,
        "rows": rows,
        "counts": dict(counts),
        "constituent_count": len(constituents),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "period": period,
    }
