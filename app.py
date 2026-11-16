"""
TradeMind - AI-Powered Trading Helper & Market Intelligence
Streamlit Application
"""
import os
from datetime import datetime
import pandas as pd
import streamlit as st

from src.config import DEFAULT_TARGETS, POPULAR_STOCKS, TIMEFRAME_OPTIONS, resolve_ticker, search_stocks
from src.data_fetcher import fetch_stock_data
from src.news_fetcher import fetch_company_news
from src.llm_analyzer import analyze_with_gemini
from src.charts import create_candlestick_chart
from src.scanner import scan_market_universe
from src.settings import (
    BUY_RSI_MAX,
    BUY_RSI_MIN,
    CACHE_TTL_SECONDS,
    DEFAULT_SELECTION_MODE,
    DEFAULT_SCANNER_INDEXES,
    DEFAULT_TIMEFRAME_LABEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LONG_SMA_PERIOD,
    NEWS_MAX_ITEMS,
    RSI_PERIOD,
    SELL_RSI_MIN,
    SEARCH_RESULT_LIMIT,
    SHORT_SMA_PERIOD,
)


def format_timestamp(value, fallback: str = "Unavailable") -> str:
    """Format provider timestamps consistently in the user's local timezone."""
    if not value:
        return fallback
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.astimezone()
        return timestamp.astimezone().strftime("%d %b %Y, %I:%M %p")
    except (TypeError, ValueError, OverflowError):
        return str(value)


def cache_duration_label() -> str:
    """Return a readable description of the configured cache duration."""
    if CACHE_TTL_SECONDS == 0:
        return "disabled"
    minutes, seconds = divmod(CACHE_TTL_SECONDS, 60)
    parts = []
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return " ".join(parts)


def open_scanner_asset(symbol: str) -> None:
    """Navigate from the scanner into the selected asset's detailed view."""
    st.session_state["selection_mode"] = "Search Any Stock"
    st.session_state["main_stock_search"] = symbol.removesuffix(".NS")


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_stock_data(ticker_symbol: str, period: str):
    """Cache market data briefly so Streamlit reruns stay responsive."""
    return fetch_stock_data(ticker_symbol, period=period)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_company_news(query: str, max_items: int = NEWS_MAX_ITEMS):
    """Cache news independently from price history."""
    return fetch_company_news(query, max_items=max_items)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_stock_search(query: str, limit: int = SEARCH_RESULT_LIMIT):
    """Cache Yahoo-backed search results while a user is exploring symbols."""
    return search_stocks(query, limit=limit)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_market_universe(period: str):
    """Cache the multi-stock scanner snapshot for the configured interval."""
    return scan_market_universe(period=period)


def render_market_scanner(period: str, timeframe_label: str) -> None:
    """Render a one-click technical overview of the default index universe."""
    scanner_universe_label = " + ".join(DEFAULT_SCANNER_INDEXES)
    st.title("Market Scanner")
    st.caption(f"{scanner_universe_label} constituents · technical screening view · no manual symbol search required")

    with st.spinner(f"Scanning the current {scanner_universe_label} universe..."):
        snapshot = load_market_universe(period)

    if snapshot.get("error"):
        st.error(snapshot["error"])
        st.info("The scanner uses the official NSE Indices constituent files. Try the refresh button in the sidebar or continue with a single asset.")
        return

    rows = snapshot.get("rows", [])
    if not rows:
        st.warning("No constituent data is available for this scan.")
        return

    with st.container(border=True):
        status_cols = st.columns(4)
        with status_cols[0]:
            st.markdown(f"<div class='status-label'>Universe</div><div class='status-value'>{scanner_universe_label}</div>", unsafe_allow_html=True)
        with status_cols[1]:
            st.markdown(f"<div class='status-label'>Unique companies</div><div class='status-value'>{snapshot.get('constituent_count', len(rows))}</div>", unsafe_allow_html=True)
        with status_cols[2]:
            st.markdown(f"<div class='status-label'>History</div><div class='status-value'>{timeframe_label}</div>", unsafe_allow_html=True)
        with status_cols[3]:
            st.markdown(f"<div class='status-label'>Snapshot loaded</div><div class='status-value'>{format_timestamp(snapshot.get('fetched_at'))}</div>", unsafe_allow_html=True)

    controls = st.columns(3)
    with controls[0]:
        universe_filter = st.selectbox(
            "Universe",
            ["All", *DEFAULT_SCANNER_INDEXES],
            key="scanner_universe",
        )
    with controls[1]:
        bucket_filter = st.selectbox("Technical bucket", ["All", "BUY", "HOLD", "SELL", "WATCH", "N/A"], key="scanner_bucket")
    with controls[2]:
        sort_by = st.selectbox("Sort by", ["Technical bucket", "1D change", "RSI", "Company"], key="scanner_sort")

    frame = pd.DataFrame(rows)
    if universe_filter != "All":
        frame = frame[frame["index"].str.contains(universe_filter, na=False)]
    if bucket_filter != "All":
        frame = frame[frame["bucket"] == bucket_filter]

    if sort_by == "1D change":
        frame = frame.sort_values("day_change_pct", ascending=False, na_position="last")
    elif sort_by == "RSI":
        frame = frame.sort_values("rsi", ascending=False, na_position="last")
    elif sort_by == "Company":
        frame = frame.sort_values("company")
    else:
        bucket_order = {"BUY": 0, "HOLD": 1, "WATCH": 2, "SELL": 3, "N/A": 4}
        frame = frame.assign(_bucket_order=frame["bucket"].map(bucket_order).fillna(5)).sort_values(["_bucket_order", "company"])

    count_cols = st.columns(5)
    counts = frame["bucket"].value_counts() if not frame.empty else pd.Series(dtype="int64")
    for column, bucket, label in zip(count_cols, ["BUY", "HOLD", "SELL", "WATCH", "N/A"], ["BUY", "HOLD", "SELL", "WATCH", "Unavailable"]):
        with column:
            st.metric(label, int(counts.get(bucket, 0)))

    if frame.empty:
        st.info("No companies match these filters.")
    else:
        table = frame[["company", "symbol", "index", "industry", "last_price", "day_change_pct", "rsi", "trend", "bucket", "status"]].rename(
            columns={
                "company": "Company",
                "symbol": "Ticker",
                "index": "Index",
                "industry": "Industry",
                "last_price": "Last Price",
                "day_change_pct": "1D %",
                "rsi": "RSI",
                "trend": "Trend",
                "bucket": "Technical bucket",
                "status": "Data",
            }
        )
        st.dataframe(
            table,
            width="stretch",
            hide_index=True,
            column_config={
                "Last Price": st.column_config.NumberColumn(format="₹%.2f"),
                "1D %": st.column_config.NumberColumn(format="%.2f%%"),
                "RSI": st.column_config.NumberColumn(format="%.1f"),
            },
        )

    with st.expander("How these buckets work", expanded=False):
        st.markdown(f"""
        The scanner uses a lightweight technical screen, not a Gemini call for every company:

        - **BUY**: bullish SMA alignment with RSI between {BUY_RSI_MIN:g} and {BUY_RSI_MAX:g}.
        - **SELL**: bearish SMA alignment with RSI above {SELL_RSI_MIN:g}.
        - **HOLD**: mixed or extended conditions that need more research.
        - **WATCH**: insufficient history for a reliable long-term alignment.

        These are screening labels, not personalised recommendations. Open a company in the detailed view for its chart, news, and optional Gemini analysis.
        """)
        st.caption("Constituent source: NSE Indices official files · Price source: Yahoo Finance")

    available = frame[frame["status"] == "OK"] if not frame.empty else frame
    if not available.empty:
        labels = [f"{row.company} ({row.symbol})" for row in available.itertuples()]
        selected_label = st.selectbox("Open a company in detailed analysis", labels, key="scanner_open_asset")
        selected_row = next(row for row in available.itertuples() if f"{row.company} ({row.symbol})" == selected_label)
        st.button(
            "Open detailed view",
            type="primary",
            key="scanner_open_button",
            on_click=open_scanner_asset,
            args=(selected_row.symbol,),
        )

# Streamlit Page Config
st.set_page_config(
    page_title="TradeMind - AI Stock Co-Pilot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .verdict-box {
        padding: 1.2rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .verdict-strong-buy, .verdict-buy {
        background-color: rgba(38, 166, 154, 0.15);
        border-left: 6px solid #26a69a;
    }
    .verdict-strong-sell, .verdict-sell {
        background-color: rgba(239, 83, 80, 0.15);
        border-left: 6px solid #ef5350;
    }
    .verdict-hold {
        background-color: rgba(255, 193, 7, 0.15);
        border-left: 6px solid #ffc107;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.04);
        border-radius: 8px;
        padding: 12px 16px;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .badge-bullish { color: #26a69a; font-weight: 600; }
    .badge-bearish { color: #ef5350; font-weight: 600; }
    .badge-neutral { color: #ffc107; font-weight: 600; }
    .status-strip {
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 10px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0 1.25rem 0;
    }
    .status-label {
        color: rgba(128, 128, 128, 0.95);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .status-value { font-weight: 600; }
    .disclaimer-note {
        color: rgba(128, 128, 128, 0.95);
        font-size: 0.86rem;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
st.sidebar.title("🧠 TradeMind")
st.sidebar.caption("AI-Powered Stock Advisory Co-Pilot")

# API key is intentionally environment-only. This avoids putting secrets in a
# browser widget and keeps local/deployed configuration consistent.
env_api_key = GEMINI_API_KEY
api_key = "" if env_api_key == "your_gemini_api_key_here" else env_api_key
configured_model = GEMINI_MODEL
with st.sidebar.expander("🤖 AI status", expanded=False):
    if api_key:
        st.success("Gemini is configured from `.env`.")
    else:
        st.warning("Add `GEMINI_API_KEY` to `.env` to enable AI analysis.")
    st.caption(f"Model: `{configured_model}`")

st.sidebar.markdown("---")
st.sidebar.subheader("Select Asset")

# Mode: Market Scanner vs Single Asset views
selection_options = ["Market Scanner", "Default Indices", "Top Indian Stocks", "Search Any Stock"]
default_selection_index = (
    selection_options.index(DEFAULT_SELECTION_MODE)
    if DEFAULT_SELECTION_MODE in selection_options
    else selection_options.index("Default Indices")
)
selection_mode = st.sidebar.radio(
    "Target Selection",
    selection_options,
    index=default_selection_index,
    key="selection_mode",
)

default_target_name, default_target_symbol = next(iter(DEFAULT_TARGETS.items()))
target_symbol = default_target_symbol
display_name = default_target_name

if selection_mode == "Market Scanner":
    st.sidebar.caption(f"Browse {' + '.join(DEFAULT_SCANNER_INDEXES)} in one view.")
elif selection_mode == "Default Indices":
    choice = st.sidebar.selectbox("Choose Index", list(DEFAULT_TARGETS.keys()))
    target_symbol = DEFAULT_TARGETS[choice]
    display_name = choice

elif selection_mode == "Top Indian Stocks":
    choice = st.sidebar.selectbox("Choose Company", list(POPULAR_STOCKS.keys()))
    target_symbol = POPULAR_STOCKS[choice]
    display_name = choice

else:
    st.sidebar.caption("Use the quick search at the top of the dashboard.")

timeframe_labels = list(TIMEFRAME_OPTIONS.keys())
default_timeframe_index = (
    timeframe_labels.index(DEFAULT_TIMEFRAME_LABEL)
    if DEFAULT_TIMEFRAME_LABEL in timeframe_labels
    else 0
)
timeframe_label = st.sidebar.selectbox("History Timeframe", timeframe_labels, index=default_timeframe_index)
timeframe = TIMEFRAME_OPTIONS[timeframe_label]

st.sidebar.markdown("---")
st.sidebar.info("💡 **TradeMind** analyzes the selected history window plus latest Google News headlines to suggest whether to Buy, Hold, or Sell.")

if st.sidebar.button("🔄 Refresh market/news data"):
    st.cache_data.clear()
    st.rerun()

# --- MAIN CONTENT ---
if selection_mode == "Market Scanner":
    render_market_scanner(timeframe, timeframe_label)
    st.stop()

if selection_mode == "Search Any Stock":
    with st.container(border=True):
        st.markdown("#### 🔍 Search any Indian stock or ticker")
        if "main_stock_search" not in st.session_state:
            st.session_state["main_stock_search"] = "Reliance"
        search_query = st.text_input(
            "Company or ticker",
            key="main_stock_search",
            label_visibility="collapsed",
            placeholder="Try Reliance, TCS, INFY, SBI...",
        )
        if not search_query.strip():
            st.info("Enter a company name or ticker to continue.")
            st.stop()

        matches = load_stock_search(search_query, limit=5)
        if matches:
            labels = [f"{m['name']} ({m['symbol']})" for m in matches]
            selected_label = st.selectbox("Select a matching stock", labels, index=0)
            chosen_match = next(
                m for m in matches if f"{m['name']} ({m['symbol']})" == selected_label
            )
            target_symbol = chosen_match["symbol"]
            display_name = chosen_match["name"]
        else:
            target_symbol, display_name = resolve_ticker(search_query)

header_left, header_right = st.columns([3, 1])
with header_left:
    st.title(f"{display_name}")
    st.caption(f"`{target_symbol}` · NSE / Indian Markets · {timeframe_label} history")
with header_right:
    st.markdown("<div class='disclaimer-note'>Research dashboard<br>AI output is not financial advice.</div>", unsafe_allow_html=True)

# Fetch Data
with st.spinner("Fetching market data and historical trends..."):
    stock_data = load_stock_data(target_symbol, period=timeframe)

if stock_data.get("error"):
    st.error(stock_data["error"])
    suggestions = load_stock_search(display_name, limit=4)
    if suggestions:
        with st.container(border=True):
            st.info("💡 **Did you mean one of these stocks?**")
            cols = st.columns(min(len(suggestions), 4))
            for idx, item in enumerate(suggestions):
                with cols[idx % len(cols)]:
                    st.markdown(f"**{item['name']}**  \n`{item['symbol']}`")
    st.stop()

metrics = stock_data["metrics"]
info = stock_data["info"]
history_df = stock_data["history"]

# --- DATA STATUS ---
with st.container(border=True):
    status_cols = st.columns(4)
    with status_cols[0]:
        st.markdown("<div class='status-label'>Price source</div><div class='status-value'>Yahoo Finance</div>", unsafe_allow_html=True)
    with status_cols[1]:
        st.markdown(f"<div class='status-label'>Observations</div><div class='status-value'>{len(history_df):,} sessions</div>", unsafe_allow_html=True)
    with status_cols[2]:
        st.markdown(f"<div class='status-label'>Market data as of</div><div class='status-value'>{format_timestamp(stock_data.get('data_as_of'), 'Latest available')}</div>", unsafe_allow_html=True)
    with status_cols[3]:
        st.markdown(f"<div class='status-label'>Loaded</div><div class='status-value'>{format_timestamp(stock_data.get('fetched_at'))}</div>", unsafe_allow_html=True)

# --- METRIC CARDS ROW ---
m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Current Price", f"₹{metrics['latest_close']:,.2f}", f"{metrics['pct_change']:+.2f}%")
with m2:
    st.metric("52W High", f"₹{metrics['high_52w']:,.2f}", f"{metrics['pct_from_52w_high']:.1f}% from price")
with m3:
    st.metric("52W Low", f"₹{metrics['low_52w']:,.2f}", f"{metrics['pct_from_52w_low']:+.1f}% above")

m4, m5, m6 = st.columns(3)
with m4:
    st.metric(f"RSI ({RSI_PERIOD})", f"{metrics['rsi']:.1f}", metrics['rsi_condition'])
with m5:
    st.metric("Trend Posture", metrics['trend_signal'])
with m6:
    pe_val = f"{info.get('pe_ratio'):.1f}" if isinstance(info.get('pe_ratio'), (int, float)) else "N/A"
    st.metric("P/E Ratio", pe_val)

if metrics.get("trend_signal") == "Insufficient history":
    st.info(f"ℹ️ **Trend note:** {metrics.get('trend_signal_detail', 'More price history is needed for long-term trend alignment.')}")
else:
    st.caption(f"Trend note: {metrics.get('trend_signal_detail', '')}")

# Multi-Year Returns Summary
if metrics.get("multi_year_returns"):
    st.markdown("**Historical Multi-Year Returns (CAGR):**")
    ret_cols = st.columns(len(metrics["multi_year_returns"]))
    for i, (period_name, ret_val) in enumerate(metrics["multi_year_returns"].items()):
        with ret_cols[i]:
            st.caption(period_name)
            st.markdown(f"**{ret_val}**")

st.markdown("---")

# Fetch News
with st.spinner("Fetching latest public news..."):
    news_items = load_company_news(display_name, max_items=NEWS_MAX_ITEMS)

# Tabs: AI Analysis, Interactive Chart, News Feed, Methodology
tab_ai, tab_chart, tab_news, tab_methodology = st.tabs([
    "🤖 AI Analysis",
    "📈 Chart",
    "📰 News",
    "🧭 Methodology & Help",
])

# --- TAB 1: AI ADVISORY ---
with tab_ai:
    st.subheader("TradeMind AI Analysis")
    st.write("A model-generated synthesis of the selected technical history and latest public news context.")

    # Button to run or rerun analysis
    run_analysis = st.button("🚀 Generate / Refresh AI View", type="primary")

    # Store analysis in session_state per ticker to prevent loss on rerun
    session_key = f"ai_analysis_{target_symbol}_{timeframe}"

    if run_analysis:
        if not api_key:
            st.error("Add `GEMINI_API_KEY` to `.env`, then restart the app to enable AI analysis.")
        else:
            with st.spinner("TradeMind LLM is evaluating the selected history and news context..."):
                analysis_result = analyze_with_gemini(info, metrics, news_items, api_key=api_key)
                if analysis_result.get("error"):
                    st.error(analysis_result["error"])
                else:
                    st.session_state[session_key] = {
                        "analysis": analysis_result["data"],
                        "generated_at": datetime.now().astimezone().isoformat(),
                        "model": analysis_result.get("model", GEMINI_MODEL),
                    }

    if session_key in st.session_state:
        stored_analysis = st.session_state[session_key]
        # Compatibility for an analysis created before the richer session
        # envelope was introduced during this session.
        if isinstance(stored_analysis, dict) and "analysis" in stored_analysis:
            ai = stored_analysis["analysis"]
            generated_at = stored_analysis.get("generated_at")
            model_used = stored_analysis.get("model")
        else:
            ai = stored_analysis
            generated_at = None
            model_used = None
        verdict = ai.get("verdict", "HOLD").upper()
        confidence = ai.get("confidence_score", 50)
        horizon = ai.get("suggested_horizon", "Medium-Term")
        news_sent = ai.get("news_sentiment", "Neutral")

        # Visual Verdict styling
        box_class = "verdict-hold"
        if "BUY" in verdict:
            box_class = "verdict-buy"
        elif "SELL" in verdict:
            box_class = "verdict-sell"

        with st.container(border=True):
            st.markdown(f"<div class='verdict-box {box_class}' role='status'><div class='status-label'>AI view</div><h2 style='margin: 0.25rem 0 0 0;'> {verdict}</h2></div>", unsafe_allow_html=True)
            result_cols = st.columns(3)
            with result_cols[0]:
                st.metric("Confidence", f"{confidence}%")
            with result_cols[1]:
                st.metric("Suggested horizon", horizon)
            with result_cols[2]:
                st.metric("News tone", news_sent)
            try:
                confidence_ratio = max(0.0, min(1.0, float(confidence) / 100))
                st.progress(confidence_ratio, text=f"Model confidence: {confidence}%")
            except (TypeError, ValueError):
                pass
            generated_label = format_timestamp(generated_at, "Current session")
            model_label = model_used or GEMINI_MODEL
            st.caption(f"Generated {generated_label} · Model `{model_label}`")

        st.warning("This is model-generated research context, not a guaranteed outcome or personalised financial advice.")
        try:
            low_confidence = float(confidence) < 60
        except (TypeError, ValueError):
            low_confidence = False
        if low_confidence:
            st.info("The model reports lower confidence. Treat this view as an area for further research, not a trading instruction.")

        # Strategic Zones
        zones = ai.get("suggested_zones", {})
        st.markdown("### Potential planning zones")
        z1, z2, z3 = st.columns(3)
        with z1:
            st.info(f"🎯 **Accumulation Zone**: {zones.get('accumulation_zone', 'N/A')}")
        with z2:
            st.success(f"📈 **Target Zone**: {zones.get('target_zone', 'N/A')}")
        with z3:
            st.warning(f"🛡️ **Stop-Loss / Risk Invalidation**: {zones.get('stop_loss_risk_level', 'N/A')}")

        # Evidence and risks
        st.markdown("### Why this view?")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🟢 Key catalysts & drivers")
            for item in ai.get("key_catalysts", []):
                st.markdown(f"- {item}")
            st.caption(f"**News Sentiment:** {news_sent} — {ai.get('sentiment_summary', '')}")

        with c2:
            st.markdown("#### 🔴 Key risks & invalidation triggers")
            for item in ai.get("key_risks", []):
                st.markdown(f"- {item}")
            st.caption(f"**Technical Summary:** {ai.get('technical_summary', '')}")

        with st.expander("📝 Read full analysis thesis", expanded=True):
            st.write(ai.get("detailed_thesis", "No thesis provided."))

    else:
        st.info("👆 Generate an AI view after reviewing the price metrics, chart, and news. You can refresh it whenever the underlying data changes.")

# --- TAB 2: CHART ---
with tab_chart:
    st.subheader(f"{display_name} Technical Chart")
    st.caption(f"{timeframe_label} · Hover for aligned price, volume, and RSI values")
    with st.expander("Chart controls", expanded=False):
        chart_control_cols = st.columns(2)
        with chart_control_cols[0]:
            show_sma50 = st.checkbox(
                f"Show {SHORT_SMA_PERIOD}-day SMA",
                value=True,
                key=f"show_sma50_{target_symbol}_{timeframe}",
            )
        with chart_control_cols[1]:
            show_sma200 = st.checkbox(
                f"Show {LONG_SMA_PERIOD}-day SMA",
                value=True,
                key=f"show_sma200_{target_symbol}_{timeframe}",
            )
    chart_fig = create_candlestick_chart(
        history_df,
        title=display_name,
        show_sma50=show_sma50,
        show_sma200=show_sma200,
    )
    st.plotly_chart(chart_fig, width="stretch", config={"displaylogo": False, "responsive": True})
    st.caption("Price is adjusted for splits/dividends where supported by the data provider. Technical indicators are for research only.")

# --- TAB 3: NEWS FEED ---
with tab_news:
    st.subheader(f"Latest Public News for {display_name}")
    st.caption("Google News RSS headlines are used as context for the AI analysis; they are not independently verified investment advice.")
    if not news_items:
        st.info("No recent news articles found via Google News RSS. Try refreshing the data or continue with technical analysis.")
    else:
        for item in news_items:
            with st.container(border=True):
                title = item.get("title", "Untitled article")
                link = item.get("link", "")
                if link:
                    st.markdown(f"#### [{title}]({link})")
                else:
                    st.markdown(f"#### {title}")
                st.caption(f"{item.get('source', 'Unknown source')} · {item.get('published', 'Publication time unavailable')}")
                if item.get("summary"):
                    with st.expander("Show summary"):
                        st.write(item["summary"])

# --- TAB 4: METHODOLOGY & HELP ---
with tab_methodology:
    st.subheader("How TradeMind works")
    st.caption("Use this section to understand the evidence, model output, and limitations behind the dashboard.")
    method_cols = st.columns(3)
    with method_cols[0]:
        st.markdown("#### 1. Price data")
        st.write("Yahoo Finance supplies the selected historical OHLC window and basic company metadata.")
    with method_cols[1]:
        st.markdown("#### 2. Technical context")
        st.write("TradeMind calculates SMA, RSI, 52-week ranges, and available historical returns locally.")
    with method_cols[2]:
        st.markdown("#### 3. AI synthesis")
        st.write("Gemini combines technical context with recent headlines and returns a validated research summary.")

    with st.expander("Open full project blueprint", expanded=False):
        knowledge_file_path = os.path.join(os.path.dirname(__file__), "KNOWLEDGE.md")
        if os.path.exists(knowledge_file_path):
            with open(knowledge_file_path, "r", encoding="utf-8") as f:
                st.markdown(f.read())
        else:
            st.info("Knowledge file not found.")

    with st.expander("Known limitations", expanded=True):
        st.markdown("""
        - Data providers can be delayed, incomplete, rate-limited, or temporarily unavailable.
        - Short history windows may not contain enough observations for long-term indicators.
        - Headlines can be incomplete or misleading; the AI summary should be checked against primary sources.
        - TradeMind does not place trades, manage portfolios, or provide personalised financial advice.
        """)

    st.info(
        f"For a fresh data pull, use **Refresh market/news data** in the sidebar. "
        f"Cached market data and news normally remain available for {cache_duration_label()}."
    )

# Disclaimer
st.markdown("---")
st.caption("⚠️ **Educational & Informational Disclaimer**: TradeMind is an artificial intelligence-driven advisory helper. It does not execute trades nor constitute certified financial advice. Stock and index investments are subject to market risks. Always conduct independent research or consult a SEBI-registered advisor before investing.")
