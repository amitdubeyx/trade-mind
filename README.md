# 🧠 TradeMind — AI-Powered Stock Advisory Co-Pilot

**TradeMind** is an intelligent stock market advisory helper for Indian equities and indices (**Nifty 50** & **Nifty Bank** by default, plus custom search for any NSE/BSE stock).

It integrates a selected historical price window with the latest Google News headlines and feeds both into **Google Gemini** to suggest whether to **BUY**, **SELL**, or **HOLD**, complete with confidence scores, entry/exit zones, and risk factors.

---

## 🚀 Key Features

* **Default Indices**: Pre-configured for **Nifty 50 (`^NSEI`)** and **Nifty Bank (`^NSEBANK`)**.
* **Market Scanner**: One-click technical overview of the current Nifty 50 and Nifty Bank constituents, with BUY/HOLD/SELL/WATCH screening buckets and filters.
* **Any Company Search**: Search any Indian company (e.g. `TATAMOTORS`, `RELIANCE`, `TCS`, `INFY`) or custom ticker.
* **Flexible Historical Data**: Preset windows range from 1 month to 10 years, with a `Max` option. `yfinance` supplies 50-day SMA, 200-day SMA, RSI (14), 52-week High/Low, and available multi-year CAGR calculations.
* **Latest News Context**: Fetches current market headlines and press updates via Google News RSS without requiring a paid news API. Gemini interprets the headlines as sentiment context.
* **Gemini LLM Decision Engine**:
  * Actionable Verdict: **STRONG BUY / BUY / HOLD / SELL / STRONG SELL**
  * Confidence score (0–100%) and suggested time horizon (Short-, Medium-, or Long-Term)
  * Strategic accumulation zones, target levels, and stop-loss invalidations
  * Key catalysts (bullish) and risks (bearish) breakdown
* **Interactive Candlestick Charts**: Three-panel Plotly charts with moving averages, volume, and RSI bands.
* **Guided Dashboard UX**: Data freshness/status indicators, responsive metric cards, chart controls, clearer AI confidence context, and a collapsible methodology/help section.

---

## 🛠️ Project Structure

```
trade-mind/
├── .env.example            # Environment variables template
├── requirements.txt        # Python dependencies
├── app.py                  # Streamlit dashboard UI
├── src/
│   ├── config.py           # Index/stock maps and ticker resolution
│   ├── data_fetcher.py     # yfinance history & technical calculations
│   ├── scanner.py          # Nifty universe scan and technical buckets
│   ├── news_fetcher.py     # Google News RSS headline fetcher
│   ├── llm_analyzer.py     # Google Gemini prompt synthesis & structured output
│   ├── settings.py         # Environment-backed runtime settings
│   └── charts.py           # Plotly candlestick, volume, moving averages & RSI
├── tests/test_core.py      # Offline regression checks for core boundaries
└── README.md
```

---

## ⚡ Quick Start

### Prerequisites

Install the following before starting:

- Git, if you want to clone the repository
- Python 3.10 or newer
- Internet access for market data, news, and Gemini analysis
- A Google Gemini API key if you want to use the AI analysis tab

Check that Python is installed:

```text
Windows:     py --version
macOS/Linux: python3 --version
```

### 1. Get the project

If Git is installed, clone the repository:

```bash
git clone https://github.com/amitdubeyx/trade-mind.git
cd trade-mind
```

Alternatively, download the ZIP or extract the shared project folder, then
open a terminal in that project folder. If your terminal is currently in the
parent directory and the folder is named `trade-mind`, use:

```bash
cd trade-mind
```

If your downloaded folder has a different name, replace `trade-mind` with that
folder name. You can also open the terminal directly from the project folder.

### 2. Create and activate a virtual environment

Using a virtual environment keeps TradeMind's packages separate from other
Python projects.

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

When activation succeeds, install the dependencies:

Windows PowerShell:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

macOS/Linux:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure Gemini AI (optional but recommended)

The dashboard's charts, technical indicators, scanner, and news feed can be
used without Gemini. The AI Analysis tab requires a Gemini API key.

Create a local `.env` file from the example:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder value:

```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

Keep `.env` private. Do not upload it, commit it, or share the API key. Restart
TradeMind after changing the key.

Optional model settings:

```ini
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_FALLBACK_MODELS=gemini-3.8-flash,gemini-2.5-flash-lite
GEMINI_TEMPERATURE=0.2
GEMINI_MAX_OUTPUT_TOKENS=2000
```

Optional TradeMind runtime settings:

```ini
TRADEMIND_CACHE_TTL_SECONDS=900
TRADEMIND_NEWS_MAX_ITEMS=8
TRADEMIND_HTTP_TIMEOUT_SECONDS=10
TRADEMIND_YAHOO_SEARCH_TIMEOUT_SECONDS=5
TRADEMIND_SCANNER_MAX_WORKERS=8
TRADEMIND_SEARCH_RESULT_LIMIT=5
TRADEMIND_DEFAULT_TARGETS=NIFTY 50=^NSEI,NIFTY BANK=^NSEBANK
TRADEMIND_TIMEFRAME_OPTIONS=1 Month=1mo,6 Months=6mo,1 Year=1y,2 Years=2y,5 Years=5y,10 Years=10y,Max=max
TRADEMIND_DEFAULT_TIMEFRAME=1 Year
TRADEMIND_DEFAULT_SELECTION_MODE=Default Indices
TRADEMIND_SCANNER_INDEXES=NIFTY 50,NIFTY BANK
TRADEMIND_NIFTY_50_CONSTITUENTS_URL=https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv
TRADEMIND_NIFTY_BANK_CONSTITUENTS_URL=https://www.niftyindices.com/IndexConstituent/ind_niftybanklist.csv
TRADEMIND_NEWS_LANGUAGE=en-IN
TRADEMIND_NEWS_COUNTRY=IN
TRADEMIND_NEWS_EDITION=IN:en
TRADEMIND_NEWS_QUERY_SUFFIX=share stock market India
TRADEMIND_SHORT_SMA_PERIOD=50
TRADEMIND_LONG_SMA_PERIOD=200
TRADEMIND_EMA_PERIOD=20
TRADEMIND_RSI_PERIOD=14
TRADEMIND_RSI_OVERBOUGHT=70
TRADEMIND_RSI_OVERSOLD=30
TRADEMIND_BUY_RSI_MIN=35
TRADEMIND_BUY_RSI_MAX=75
TRADEMIND_SELL_RSI_MIN=30
TRADEMIND_WEEK_LOOKBACK_TRADING_DAYS=252
TRADEMIND_TRADING_DAYS_PER_YEAR=252
TRADEMIND_CAGR_YEARS=1,3,5,10
TRADEMIND_NEWS_SUMMARY_MAX_CHARS=800
```

The defaults in `.env.example` are suitable for most users. The application
also has the same safe fallback values in `src/settings.py`, so optional
entries can be omitted. Change these only when you need to tune cache duration,
network timeouts, scanner speed, result count, technical indicators, or Gemini
output behavior.

### 4. Start the dashboard

Run this command from the project folder while the virtual environment is
active:

```bash
streamlit run app.py
```

Streamlit will display a local URL, usually `http://localhost:8501`. Open that
URL in your browser.

### 5. Run the tests

With the virtual environment active, run:

```bash
python -m unittest discover -s tests -v
```

The same test suite runs automatically through GitHub Actions for pushes and
pull requests.

### Using the dashboard

- **Market Scanner**: Review Nifty 50 and Nifty Bank constituents using local
  technical screening.
- **Default Indices**: Analyze Nifty 50 or Nifty Bank.
- **Top Indian Stocks**: Select a commonly followed Indian stock.
- **Search Any Stock**: Search for another NSE/BSE company or ticker.
- **AI Analysis**: Generate a Gemini-based research summary after reviewing the
  price history and news.
- **Refresh market/news data**: Use the sidebar refresh control when you want
  to bypass the configured cache interval (15 minutes by default).

The scanner reads current constituent files from [NSE Indices](https://www.niftyindices.com/indices/equity/broad-based-indices/nifty--50)
and [Nifty Bank](https://www.niftyindices.com/indices/equity/sectoral-indices/nifty-bank),
then applies a local technical screen. It does not call Gemini for every row;
open a company in the detailed view when you want full chart, news, and AI
context.

Scanner buckets are deliberately simple screening labels:

- `BUY`: bullish SMA alignment with RSI between the configured buy thresholds
  (35–75 by default).
- `SELL`: bearish SMA alignment with RSI above the configured sell threshold
  (30 by default).
- `HOLD`: mixed or extended technical conditions.
- `WATCH`: insufficient history for reliable long-term alignment.

These buckets are not backtested recommendations or personalised financial advice.

### Troubleshooting

- **`python` or `py` is not recognized**: Install Python from
  [python.org](https://www.python.org/downloads/) and enable “Add Python to
  PATH” on Windows.
- **PowerShell blocks activation**: Run
  `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`, then
  activate the environment again.
- **`ModuleNotFoundError`**: Confirm that `.venv` is active and run
  `python -m pip install -r requirements.txt` again.
- **Gemini is unavailable**: Confirm that `.env` is beside `app.py`, the key is
  valid, and the app has been restarted.
- **The browser does not open automatically**: Copy the local URL printed by
  Streamlit into your browser.
- **A provider returns no data**: Check your internet connection and retry
  later; public data providers can be delayed or rate-limited.

## Current scope and next milestones

TradeMind is currently a research dashboard, not a trading system. The first
version combines Yahoo Finance OHLC history, technical indicators, Google News
RSS headlines, and Gemini synthesis. The AI response is advisory text only;
the application does not place orders, persist portfolios, or backtest signals.

The most valuable next steps are:

1. Add a fundamentals data source with explicit freshness timestamps.
2. Add signal backtesting and paper-trading evaluation before trusting verdicts.
3. Persist watchlists and prior analyses so users can compare changes over time.
4. Add observability for provider failures, rate limits, and stale data.

---

## ⚠️ Disclaimer
*TradeMind is an educational and analytical decision-support tool. It does not place automated trades and is not certified financial advice. Stock trading involves market risk.*
