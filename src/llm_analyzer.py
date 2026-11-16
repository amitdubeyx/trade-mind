"""
LLM Analyzer module for TradeMind.

The model is used for synthesis, while the application owns the data
collection and validation boundaries. That keeps malformed model output from
breaking the dashboard and makes the selected Gemini model configurable.
"""
import json
import math
from typing import Any, Dict, List

from google import genai
from google.genai import types

from src.settings import (
    GEMINI_API_KEY,
    GEMINI_FALLBACK_MODELS,
    GEMINI_MAX_OUTPUT_TOKENS,
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    LONG_SMA_PERIOD,
    NEWS_MAX_ITEMS,
    RSI_PERIOD,
    SHORT_SMA_PERIOD,
)


VALID_VERDICTS = {"STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"}
VALID_SENTIMENTS = {"BULLISH": "Bullish", "NEUTRAL": "Neutral", "BEARISH": "Bearish"}


def _string_list(value: Any, fallback: List[str]) -> List[str]:
    """Normalise model-generated bullet fields into a safe list of strings."""
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items[:6] or fallback
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return fallback


def normalise_analysis(data: Any) -> Dict[str, Any]:
    """Validate and fill the fields consumed by the Streamlit UI."""
    if not isinstance(data, dict):
        raise ValueError("Gemini returned a JSON value other than an object")

    verdict = str(data.get("verdict", "HOLD")).strip().upper()
    if verdict not in VALID_VERDICTS:
        verdict = "HOLD"

    try:
        confidence = float(data.get("confidence_score", 50))
    except (TypeError, ValueError):
        confidence = 50.0
    if not math.isfinite(confidence):
        confidence = 50.0
    confidence = max(0.0, min(100.0, confidence))
    confidence_value = int(confidence) if confidence.is_integer() else round(confidence, 1)

    sentiment_key = str(data.get("news_sentiment", "Neutral")).strip().upper()
    sentiment = VALID_SENTIMENTS.get(sentiment_key, "Neutral")

    raw_zones = data.get("suggested_zones")
    zones = raw_zones if isinstance(raw_zones, dict) else {}

    return {
        "verdict": verdict,
        "confidence_score": confidence_value,
        "suggested_horizon": str(data.get("suggested_horizon", "Medium-Term (1-6 Months)")),
        "news_sentiment": sentiment,
        "sentiment_summary": str(data.get("sentiment_summary", "No sentiment summary provided.")),
        "technical_summary": str(data.get("technical_summary", "No technical summary provided.")),
        "key_catalysts": _string_list(data.get("key_catalysts"), ["No specific catalyst provided."]),
        "key_risks": _string_list(data.get("key_risks"), ["No specific risk provided."]),
        "suggested_zones": {
            "accumulation_zone": str(zones.get("accumulation_zone", "N/A")),
            "target_zone": str(zones.get("target_zone", "N/A")),
            "stop_loss_risk_level": str(zones.get("stop_loss_risk_level", "N/A")),
        },
        "detailed_thesis": str(data.get("detailed_thesis", "No thesis provided.")),
    }


def _parse_json_response(content: str) -> Dict[str, Any]:
    """Parse JSON even if a provider wraps it in a markdown fence."""
    if not content or not content.strip():
        raise ValueError("Gemini returned an empty response")

    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```")
        cleaned = cleaned.removesuffix("```").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Be tolerant of a short preamble despite the prompt requiring JSON.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Gemini response did not contain a JSON object")
        return json.loads(cleaned[start : end + 1])


def _is_model_selection_error(error: Exception) -> bool:
    message = str(error).casefold()
    return any(
        marker in message
        for marker in ("not found", "not supported", "unknown model", "invalid model", "404")
    )


def analyze_with_gemini(
    stock_info: Dict[str, Any],
    metrics: Dict[str, Any],
    news_items: List[Dict[str, Any]],
    api_key: str = None,
) -> Dict[str, Any]:
    """Synthesize market metrics and news into a validated advisory object."""
    key = (api_key or GEMINI_API_KEY or "").strip()
    if not key or key == "your_gemini_api_key_here":
        return {
            "error": "Google Gemini API key not found. Please provide an API key in the sidebar or in your .env file."
        }

    news_text = (
        "\n".join(
            f"- [{item.get('source')}] {item.get('title')} ({item.get('published', '')})"
            for item in news_items[:NEWS_MAX_ITEMS]
        )
        if news_items
        else "No recent public news articles found."
    )

    returns_text = ", ".join(
        f"{key}: {value}" for key, value in metrics.get("multi_year_returns", {}).items()
    ) or "N/A"

    prompt = f"""
You are an expert Senior Quantitative Analyst and Stock Market Sentiment Strategist specializing in the Indian Stock Market (NSE/BSE, Nifty 50, Nifty Bank, and major equities).

Analyze the following market data and recent public news for:
COMPANY / ASSET: {stock_info.get('name')}
SECTOR: {stock_info.get('sector', 'N/A')}
MARKET CAP: {stock_info.get('market_cap', 'N/A')}
TRAILING P/E: {stock_info.get('pe_ratio', 'N/A')}

--- TECHNICAL & HISTORICAL METRICS ---
- Current Price: ₹{metrics.get('latest_close', 0):.2f}
- Today's Change: {metrics.get('pct_change', 0):+.2f}%
- 52-Week High: ₹{metrics.get('high_52w', 0):.2f} ({metrics.get('pct_from_52w_high', 0):.1f}% from high)
- 52-Week Low: ₹{metrics.get('low_52w', 0):.2f} ({metrics.get('pct_from_52w_low', 0):+.1f}% from low)
- {RSI_PERIOD}-Day RSI: {metrics.get('rsi', 50):.1f} ({metrics.get('rsi_condition', 'Neutral')})
- {SHORT_SMA_PERIOD}-Day SMA: ₹{metrics.get('sma_short', 0) if metrics.get('sma_short') else 'N/A'}
- {LONG_SMA_PERIOD}-Day SMA: ₹{metrics.get('sma_long', 0) if metrics.get('sma_long') else 'N/A'}
- Technical Posture: {metrics.get('trend_signal', 'Neutral')}
- Technical Posture Detail: {metrics.get('trend_signal_detail', 'N/A')}
- Observations Used: {metrics.get('observations', 'N/A')}
- Historical Returns: {returns_text}

--- RECENT PUBLIC NEWS & HEADLINES ---
{news_text}

--- YOUR TASK ---
Analyze the selected technical history and the latest news context.
Provide a clear, unbiased suggestion on whether an investor or trader should BUY, SELL, or HOLD.
Be balanced, realistic, and objective. Never imply certainty or guaranteed returns. If history is insufficient for a requested indicator, say so explicitly.

You must respond in valid JSON matching this schema:
{{
  "verdict": "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL",
  "confidence_score": 85,
  "suggested_horizon": "Short-Term (1-4 Weeks)" | "Medium-Term (1-6 Months)" | "Long-Term (1-3 Years)",
  "news_sentiment": "Bullish" | "Neutral" | "Bearish",
  "sentiment_summary": "1-2 sentences summarizing news sentiment",
  "technical_summary": "1-2 sentences summarizing chart trend and momentum",
  "key_catalysts": ["catalyst 1", "catalyst 2", "catalyst 3"],
  "key_risks": ["risk 1", "risk 2", "risk 3"],
  "suggested_zones": {{
     "accumulation_zone": "e.g. ₹2,450 - ₹2,500",
     "target_zone": "e.g. ₹2,750 - ₹2,850",
     "stop_loss_risk_level": "e.g. ₹2,380"
  }},
  "detailed_thesis": "A comprehensive paragraph explaining the overall rationale integrating historical performance, valuation, and current news triggers."
}}

Output ONLY the JSON object, with no markdown backticks or extra text outside the JSON.
"""

    preferred_model = GEMINI_MODEL
    fallback_models = GEMINI_FALLBACK_MODELS
    models_to_try = list(dict.fromkeys([preferred_model, *fallback_models]))
    last_error = None

    try:
        client = genai.Client(api_key=key)
        for model_index, model_name in enumerate(models_to_try):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=GEMINI_TEMPERATURE,
                        max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
                    ),
                )

                data = normalise_analysis(_parse_json_response(response.text))
                return {"data": data, "error": None, "model": model_name}

            except Exception as error:
                last_error = error
                # Do not burn multiple requests on an invalid API key, quota
                # error, or malformed response. Only model selection errors
                # are safe to retry with a configured fallback model.
                if model_index >= len(models_to_try) - 1 or not _is_model_selection_error(error):
                    break

        return {"error": f"Gemini API Error ({preferred_model}): {str(last_error)}"}

    except Exception as error:
        return {"error": f"Failed to initialize Gemini client: {str(error)}"}
