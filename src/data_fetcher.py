"""
Data Fetcher module for TradeMind.

The module keeps network access at the boundary and returns plain Python
metrics alongside the pandas history used by the chart.  Indicators are
calculated locally so they are deterministic and easy to test.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import yfinance as yf
import pandas as pd
import numpy as np

from src.settings import (
    CAGR_YEARS,
    DEFAULT_PERIOD,
    EMA_COLUMN,
    EMA_PERIOD,
    HTTP_TIMEOUT_SECONDS,
    LONG_SMA_PERIOD,
    RSI_COLUMN,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    RSI_PERIOD,
    SHORT_SMA_PERIOD,
    SMA_LONG_COLUMN,
    SMA_SHORT_COLUMN,
    TRADING_DAYS_PER_YEAR,
    WEEK_LOOKBACK_TRADING_DAYS,
)


def calculate_rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Calculate a Wilder-style Relative Strength Index (RSI).

    Using exponential smoothing is closer to the RSI shown by most charting
    platforms than a simple rolling average.  The explicit zero-loss handling
    also makes a continuously rising series correctly report RSI 100 rather
    than a value just below it.
    """
    if period <= 0:
        raise ValueError("RSI period must be positive")

    delta = series.astype(float).diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    average_gain = gains.ewm(
        alpha=1 / period, adjust=False, min_periods=period
    ).mean()
    average_loss = losses.ewm(
        alpha=1 / period, adjust=False, min_periods=period
    ).mean()

    relative_strength = average_gain / average_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + relative_strength))
    rsi = rsi.mask((average_loss == 0) & (average_gain > 0), 100.0)
    rsi = rsi.mask((average_loss == 0) & (average_gain == 0), 50.0)
    return rsi.clip(lower=0, upper=100)


def _normalise_history(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise yfinance output, including occasional MultiIndex columns."""
    if isinstance(df.columns, pd.MultiIndex):
        first_level = [str(value) for value in df.columns.get_level_values(0)]
        if any(field in first_level for field in ("Open", "High", "Low", "Close")):
            df = df.copy()
            df.columns = first_level
        else:
            df = df.copy()
            df.columns = [str(value) for value in df.columns.get_level_values(-1)]

    required_columns = {"Open", "High", "Low", "Close"}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Price history is missing required columns: {missing}")

    return df.sort_index().dropna(subset=["Open", "High", "Low", "Close"])


def _as_float(value: Any) -> Optional[float]:
    """Convert scalar-like values to float while preserving missing values."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _calculate_cagrs(close: pd.Series, latest_close: float) -> Dict[str, str]:
    """Calculate annualised returns only when a complete lookback is present."""
    returns: Dict[str, str] = {}
    for years in CAGR_YEARS:
        trading_days = years * TRADING_DAYS_PER_YEAR
        # There must be a start price plus the requested number of intervals.
        if len(close) <= trading_days:
            continue

        past_price = _as_float(close.iloc[-(trading_days + 1)])
        if past_price is None or past_price <= 0 or latest_close <= 0:
            continue

        cagr = ((latest_close / past_price) ** (1 / years) - 1) * 100
        returns[f"{years}Y CAGR"] = f"{cagr:.1f}%"

    return returns

def fetch_stock_data(
    ticker_symbol: str,
    period: str = DEFAULT_PERIOD,
    include_info: bool = True,
) -> Dict[str, Any]:
    """
    Fetches historical stock/index data and key fundamental/technical indicators.
    Returns:
        dict with keys: 'ticker', 'info', 'history', 'metrics', 'error'
    """
    try:
        clean_symbol = ticker_symbol.strip().upper()
        ticker = yf.Ticker(clean_symbol)
        # Adjusted prices make multi-year comparisons meaningful across stock
        # splits and dividends.  A timeout keeps a stalled data provider from
        # freezing the dashboard indefinitely.
        df = ticker.history(period=period, auto_adjust=True, timeout=HTTP_TIMEOUT_SECONDS)

        if df.empty:
            return {"error": f"No data found for symbol '{clean_symbol}'. Please verify the ticker."}

        df = _normalise_history(df)
        if df.empty:
            return {"error": f"No usable price history found for symbol '{clean_symbol}'."}

        # Calculate Technical Indicators
        df[SMA_SHORT_COLUMN] = df["Close"].rolling(window=SHORT_SMA_PERIOD).mean()
        df[SMA_LONG_COLUMN] = df["Close"].rolling(window=LONG_SMA_PERIOD).mean()
        df[EMA_COLUMN] = df["Close"].ewm(span=EMA_PERIOD, adjust=False).mean()
        df[RSI_COLUMN] = calculate_rsi(df["Close"], period=RSI_PERIOD)

        # Basic statistics
        latest_close = _as_float(df["Close"].iloc[-1])
        if latest_close is None:
            return {"error": f"Latest price is unavailable for symbol '{clean_symbol}'."}

        prev_close = _as_float(df["Close"].iloc[-2]) if len(df) > 1 else latest_close
        prev_close = prev_close if prev_close is not None else latest_close
        price_change = latest_close - prev_close
        pct_change = (price_change / prev_close) * 100 if prev_close != 0 else 0.0

        high_52w = _as_float(df["High"].tail(WEEK_LOOKBACK_TRADING_DAYS).max())
        low_52w = _as_float(df["Low"].tail(WEEK_LOOKBACK_TRADING_DAYS).min())
        if high_52w is None or low_52w is None or high_52w <= 0 or low_52w <= 0:
            return {"error": f"Invalid high/low prices returned for symbol '{clean_symbol}'."}

        latest_rsi = _as_float(df[RSI_COLUMN].iloc[-1])
        latest_rsi = latest_rsi if latest_rsi is not None else 50.0
        latest_sma50 = _as_float(df[SMA_SHORT_COLUMN].iloc[-1])
        latest_sma200 = _as_float(df[SMA_LONG_COLUMN].iloc[-1])

        # Multi-year overview, only when the selected period contains the
        # complete lookback plus a start observation.
        multi_year_returns = _calculate_cagrs(df["Close"], latest_close)

        # General info (Name, Sector, PE, Market Cap). Bulk scanners can skip
        # this slower optional endpoint and use the official index metadata.
        info = {"name": clean_symbol, "currency": "INR"}
        if include_info:
            try:
                raw_info = ticker.info
                info = {
                    "name": raw_info.get("shortName") or raw_info.get("longName") or clean_symbol,
                    "sector": raw_info.get("sector", "N/A"),
                    "industry": raw_info.get("industry", "N/A"),
                    "market_cap": raw_info.get("marketCap", "N/A"),
                    "pe_ratio": raw_info.get("trailingPE", "N/A"),
                    "forward_pe": raw_info.get("forwardPE", "N/A"),
                    "currency": raw_info.get("currency", "INR")
                }
            except Exception:
                info = {"name": clean_symbol, "currency": "INR"}

        # Technical signals summary
        if latest_sma50 is not None and latest_sma200 is not None:
            trend_signal = "Bullish" if latest_sma50 > latest_sma200 else "Bearish"
            trend_signal_detail = (
                f"{SHORT_SMA_PERIOD}-day SMA is above the {LONG_SMA_PERIOD}-day SMA."
                if trend_signal == "Bullish"
                else f"{SHORT_SMA_PERIOD}-day SMA is below the {LONG_SMA_PERIOD}-day SMA."
            )
        elif latest_sma50 is not None:
            trend_signal = "Insufficient history"
            short_term_direction = "above" if latest_close > latest_sma50 else "below"
            trend_signal_detail = (
                f"Price is {short_term_direction} the {SHORT_SMA_PERIOD}-day SMA; "
                f"{LONG_SMA_PERIOD}-day SMA is not available for this timeframe."
            )
        else:
            trend_signal = "Insufficient history"
            trend_signal_detail = (
                f"Not enough observations to calculate a {SHORT_SMA_PERIOD}-day or "
                f"{LONG_SMA_PERIOD}-day SMA."
            )

        if latest_rsi > RSI_OVERBOUGHT:
            rsi_condition = f"Overbought (> {RSI_OVERBOUGHT:g})"
        elif latest_rsi < RSI_OVERSOLD:
            rsi_condition = f"Oversold (< {RSI_OVERSOLD:g})"
        else:
            rsi_condition = f"Neutral ({latest_rsi:.1f})"

        metrics = {
            "latest_close": latest_close,
            "prev_close": prev_close,
            "price_change": price_change,
            "pct_change": pct_change,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "pct_from_52w_high": ((latest_close - high_52w) / high_52w) * 100,
            "pct_from_52w_low": ((latest_close - low_52w) / low_52w) * 100,
            "rsi": latest_rsi,
            "rsi_14": latest_rsi,
            "rsi_condition": rsi_condition,
            "sma_short": latest_sma50,
            "sma_long": latest_sma200,
            "sma_50": latest_sma50,
            "sma_200": latest_sma200,
            "trend_signal": trend_signal,
            "trend_signal_detail": trend_signal_detail,
            "observations": len(df),
            "multi_year_returns": multi_year_returns
        }

        return {
            "ticker": clean_symbol,
            "info": info,
            "history": df,
            "metrics": metrics,
            "data_as_of": df.index[-1].isoformat(),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "error": None
        }

    except Exception as e:
        return {"error": f"Failed to fetch stock data: {str(e)}"}
