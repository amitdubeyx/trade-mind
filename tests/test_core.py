import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from src.config import fetch_index_constituents, search_stocks
from src.data_fetcher import calculate_rsi, fetch_stock_data
from src.llm_analyzer import _parse_json_response, normalise_analysis
from src.news_fetcher import fetch_company_news
from src.charts import create_candlestick_chart
from src.scanner import technical_bucket


class DataFetcherTests(unittest.TestCase):
    def test_rsi_handles_continuous_gain(self):
        prices = pd.Series(range(1, 40), dtype=float)
        rsi = calculate_rsi(prices)
        self.assertEqual(float(rsi.iloc[-1]), 100.0)

    def test_short_history_is_not_marked_bearish(self):
        dates = pd.date_range("2026-01-01", periods=30, freq="D")
        close = pd.Series(range(100, 130), index=dates, dtype=float)
        history = pd.DataFrame(
            {
                "Open": close - 1,
                "High": close + 1,
                "Low": close - 2,
                "Close": close,
                "Volume": 1000,
            }
        )

        fake_ticker = MagicMock()
        fake_ticker.history.return_value = history
        fake_ticker.info = {"shortName": "Test Asset", "currency": "INR"}

        with patch("src.data_fetcher.yf.Ticker", return_value=fake_ticker):
            result = fetch_stock_data("TEST.NS", period="1mo")

        self.assertIsNone(result.get("error"))
        self.assertEqual(result["metrics"]["trend_signal"], "Insufficient history")
        self.assertIn("Not enough observations", result["metrics"]["trend_signal_detail"])


class SearchTests(unittest.TestCase):
    def test_short_ticker_does_not_return_irrelevant_fuzzy_matches(self):
        with patch("src.config.requests.get") as get:
            result = search_stocks("TCS", limit=3)

        self.assertEqual(result[0]["symbol"], "TCS.NS")
        self.assertNotIn("ITC.NS", {item["symbol"] for item in result})
        get.assert_not_called()

    def test_official_constituent_csv_is_normalised(self):
        response = MagicMock()
        response.content = b"Company Name,Industry,Symbol,Series,ISIN Code\nExample Bank,Financial Services,EXBANK,EQ,INE000000000\n"
        response.raise_for_status.return_value = None

        with patch("src.config.requests.get", return_value=response):
            result = fetch_index_constituents("NIFTY BANK")

        self.assertEqual(result[0]["symbol"], "EXBANK.NS")
        self.assertEqual(result[0]["index"], "NIFTY BANK")


class NewsTests(unittest.TestCase):
    def test_news_is_deduplicated_and_source_is_extracted(self):
        rss = b"""<?xml version='1.0'?><rss><channel>
        <item><title>Markets rise - Example Source</title><link>https://example.com/1</link>
        <pubDate>Sun, 15 Nov 2026 10:00:00 GMT</pubDate><description>&lt;b&gt;Positive&lt;/b&gt; update</description>
        <source url='https://example.com'>Example Source</source></item>
        <item><title>Markets rise - Example Source</title><link>https://example.com/1</link></item>
        </channel></rss>"""
        response = MagicMock()
        response.content = rss
        response.raise_for_status.return_value = None

        with patch("src.news_fetcher.requests.get", return_value=response):
            result = fetch_company_news("Nifty 50", max_items=10)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"], "Example Source")
        self.assertEqual(result[0]["summary"], "Positive update")


class LlmOutputTests(unittest.TestCase):
    def test_model_output_is_clamped_and_completed(self):
        result = normalise_analysis(
            {
                "verdict": "something else",
                "confidence_score": 120,
                "news_sentiment": "bearish",
                "key_catalysts": "One catalyst",
            }
        )
        self.assertEqual(result["verdict"], "HOLD")
        self.assertEqual(result["confidence_score"], 100)
        self.assertEqual(result["news_sentiment"], "Bearish")
        self.assertEqual(result["key_catalysts"], ["One catalyst"])
        self.assertEqual(result["suggested_zones"]["target_zone"], "N/A")

    def test_json_parser_accepts_markdown_fence_and_preamble(self):
        self.assertEqual(_parse_json_response("```json\n{\"ok\": true}\n```")["ok"], True)
        self.assertEqual(_parse_json_response("Here is the result: {\"ok\": true}")["ok"], True)


class ChartTests(unittest.TestCase):
    def test_chart_contains_volume_panel(self):
        dates = pd.date_range("2026-01-01", periods=5, freq="D")
        prices = pd.Series([100, 102, 101, 104, 103], index=dates)
        frame = pd.DataFrame(
            {
                "Open": prices - 1,
                "High": prices + 1,
                "Low": prices - 2,
                "Close": prices,
                "Volume": [100, 120, 90, 150, 110],
                "SMA_50": prices,
                "SMA_200": prices,
                "RSI_14": [50, 55, 48, 62, 57],
            }
        )
        figure = create_candlestick_chart(frame, title="Test")
        self.assertIn("Volume", {trace.name for trace in figure.data})
        annotation_text = {annotation.text for annotation in figure.layout.annotations}
        self.assertIn("Trading Volume", annotation_text)
        self.assertIn("Relative Strength Index (RSI 14)", annotation_text)


class ScannerTests(unittest.TestCase):
    def test_technical_buckets_are_deterministic(self):
        self.assertEqual(technical_bucket({"trend_signal": "Bullish", "rsi_14": 55}), "BUY")
        self.assertEqual(technical_bucket({"trend_signal": "Bearish", "rsi_14": 55}), "SELL")
        self.assertEqual(technical_bucket({"trend_signal": "Bullish", "rsi_14": 80}), "HOLD")
        self.assertEqual(technical_bucket({"trend_signal": "Insufficient history", "rsi_14": 50}), "WATCH")


if __name__ == "__main__":
    unittest.main()
