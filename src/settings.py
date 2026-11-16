"""Runtime settings loaded from environment variables with safe defaults."""

import os
from typing import Dict, List, Tuple

from dotenv import load_dotenv


load_dotenv()


def _env_int(name: str, default: int, minimum: int = 0, maximum: int = None) -> int:
    """Read a bounded integer setting without allowing invalid values to crash startup."""
    raw_value = os.getenv(name, "").strip()
    try:
        value = int(raw_value) if raw_value else default
    except ValueError:
        value = default

    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _env_float(name: str, default: float, minimum: float = 0.0, maximum: float = None) -> float:
    """Read a bounded floating-point setting with a safe fallback."""
    raw_value = os.getenv(name, "").strip()
    try:
        value = float(raw_value) if raw_value else default
    except ValueError:
        value = default

    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _env_csv(name: str, default: str) -> List[str]:
    """Read a comma-separated setting and remove empty entries."""
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _env_mapping(name: str, default: str) -> Dict[str, str]:
    """Read comma-separated ``label=value`` pairs from an environment variable."""
    raw_value = os.getenv(name, default)
    mapping: Dict[str, str] = {}
    for item in raw_value.split(","):
        label, separator, value = item.partition("=")
        if separator and label.strip() and value.strip():
            mapping[label.strip()] = value.strip()
    return mapping or _env_mapping_from_string(default)


def _env_mapping_from_string(value: str) -> Dict[str, str]:
    """Parse a mapping fallback without reading the environment again."""
    mapping: Dict[str, str] = {}
    for item in value.split(","):
        label, separator, mapped_value = item.partition("=")
        if separator and label.strip() and mapped_value.strip():
            mapping[label.strip()] = mapped_value.strip()
    return mapping


def _env_int_csv(name: str, default: str) -> Tuple[int, ...]:
    """Read a comma-separated list of bounded positive integers."""
    values: List[int] = []
    for item in _env_csv(name, default):
        try:
            value = int(item)
        except ValueError:
            continue
        if value > 0:
            values.append(value)
    return tuple(values) or tuple(int(item) for item in default.split(","))


# Secrets and provider/model settings.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"
GEMINI_FALLBACK_MODELS = _env_csv(
    "GEMINI_FALLBACK_MODELS",
    "gemini-3.8-flash,gemini-2.5-flash-lite",
)
GEMINI_TEMPERATURE = _env_float("GEMINI_TEMPERATURE", 0.2, minimum=0.0, maximum=2.0)
GEMINI_MAX_OUTPUT_TOKENS = _env_int("GEMINI_MAX_OUTPUT_TOKENS", 2000, minimum=1, maximum=8192)

# Runtime tuning settings. These can be changed per machine/deployment without
# editing application code.
CACHE_TTL_SECONDS = _env_int("TRADEMIND_CACHE_TTL_SECONDS", 900, minimum=0)
NEWS_MAX_ITEMS = _env_int("TRADEMIND_NEWS_MAX_ITEMS", 8, minimum=1, maximum=50)
SEARCH_RESULT_LIMIT = _env_int("TRADEMIND_SEARCH_RESULT_LIMIT", 5, minimum=1, maximum=20)
HTTP_TIMEOUT_SECONDS = _env_int("TRADEMIND_HTTP_TIMEOUT_SECONDS", 10, minimum=1, maximum=120)
YAHOO_SEARCH_TIMEOUT_SECONDS = _env_int(
    "TRADEMIND_YAHOO_SEARCH_TIMEOUT_SECONDS", 5, minimum=1, maximum=120
)
SCANNER_MAX_WORKERS = _env_int("TRADEMIND_SCANNER_MAX_WORKERS", 8, minimum=1, maximum=32)

# Dashboard defaults and structured options.
DEFAULT_TARGETS = _env_mapping(
    "TRADEMIND_DEFAULT_TARGETS",
    "NIFTY 50=^NSEI,NIFTY BANK=^NSEBANK",
)
TIMEFRAME_OPTIONS = _env_mapping(
    "TRADEMIND_TIMEFRAME_OPTIONS",
    "1 Month=1mo,6 Months=6mo,1 Year=1y,2 Years=2y,5 Years=5y,10 Years=10y,Max=max",
)
DEFAULT_TIMEFRAME_LABEL = os.getenv("TRADEMIND_DEFAULT_TIMEFRAME", "1 Year").strip() or "1 Year"
DEFAULT_PERIOD = TIMEFRAME_OPTIONS.get(DEFAULT_TIMEFRAME_LABEL, "1y")
DEFAULT_SELECTION_MODE = os.getenv("TRADEMIND_DEFAULT_SELECTION_MODE", "Default Indices").strip() or "Default Indices"
_configured_scanner_indexes = _env_csv("TRADEMIND_SCANNER_INDEXES", "NIFTY 50,NIFTY BANK")
DEFAULT_SCANNER_INDEXES = tuple(_configured_scanner_indexes or ("NIFTY 50", "NIFTY BANK"))
NIFTY_50_CONSTITUENTS_URL = os.getenv(
    "TRADEMIND_NIFTY_50_CONSTITUENTS_URL",
    "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv",
).strip()
NIFTY_BANK_CONSTITUENTS_URL = os.getenv(
    "TRADEMIND_NIFTY_BANK_CONSTITUENTS_URL",
    "https://www.niftyindices.com/IndexConstituent/ind_niftybanklist.csv",
).strip()
NEWS_LANGUAGE = os.getenv("TRADEMIND_NEWS_LANGUAGE", "en-IN").strip() or "en-IN"
NEWS_COUNTRY = os.getenv("TRADEMIND_NEWS_COUNTRY", "IN").strip() or "IN"
NEWS_EDITION = os.getenv("TRADEMIND_NEWS_EDITION", "IN:en").strip() or "IN:en"
NEWS_QUERY_SUFFIX = os.getenv(
    "TRADEMIND_NEWS_QUERY_SUFFIX", "share stock market India"
).strip()

# Technical-analysis settings.
SHORT_SMA_PERIOD = _env_int("TRADEMIND_SHORT_SMA_PERIOD", 50, minimum=2, maximum=500)
LONG_SMA_PERIOD = _env_int("TRADEMIND_LONG_SMA_PERIOD", 200, minimum=2, maximum=1000)
EMA_PERIOD = _env_int("TRADEMIND_EMA_PERIOD", 20, minimum=2, maximum=500)
RSI_PERIOD = _env_int("TRADEMIND_RSI_PERIOD", 14, minimum=2, maximum=100)
RSI_OVERBOUGHT = _env_float("TRADEMIND_RSI_OVERBOUGHT", 70.0, minimum=50.0, maximum=100.0)
RSI_OVERSOLD = _env_float("TRADEMIND_RSI_OVERSOLD", 30.0, minimum=0.0, maximum=50.0)
BUY_RSI_MIN = _env_float("TRADEMIND_BUY_RSI_MIN", 35.0, minimum=0.0, maximum=100.0)
BUY_RSI_MAX = _env_float("TRADEMIND_BUY_RSI_MAX", 75.0, minimum=0.0, maximum=100.0)
SELL_RSI_MIN = _env_float("TRADEMIND_SELL_RSI_MIN", 30.0, minimum=0.0, maximum=100.0)
WEEK_LOOKBACK_TRADING_DAYS = _env_int(
    "TRADEMIND_WEEK_LOOKBACK_TRADING_DAYS", 252, minimum=20, maximum=1000
)
TRADING_DAYS_PER_YEAR = _env_int(
    "TRADEMIND_TRADING_DAYS_PER_YEAR", 252, minimum=200, maximum=366
)
CAGR_YEARS = _env_int_csv("TRADEMIND_CAGR_YEARS", "1,3,5,10")
NEWS_SUMMARY_MAX_CHARS = _env_int(
    "TRADEMIND_NEWS_SUMMARY_MAX_CHARS", 800, minimum=100, maximum=5000
)

# Keep related thresholds coherent even if an invalid combination is supplied
# through a deployment-specific .env file.
if LONG_SMA_PERIOD <= SHORT_SMA_PERIOD:
    LONG_SMA_PERIOD = max(SHORT_SMA_PERIOD + 1, 200)
if RSI_OVERSOLD >= RSI_OVERBOUGHT:
    RSI_OVERSOLD, RSI_OVERBOUGHT = 30.0, 70.0
if BUY_RSI_MIN >= BUY_RSI_MAX:
    BUY_RSI_MIN, BUY_RSI_MAX = 35.0, 75.0

SMA_SHORT_COLUMN = f"SMA_{SHORT_SMA_PERIOD}"
SMA_LONG_COLUMN = f"SMA_{LONG_SMA_PERIOD}"
EMA_COLUMN = f"EMA_{EMA_PERIOD}"
RSI_COLUMN = f"RSI_{RSI_PERIOD}"

