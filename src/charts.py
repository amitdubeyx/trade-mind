"""
Charts module for TradeMind
Creates Plotly interactive charts with candlesticks, SMAs, Volume, and RSI subplots.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from src.settings import (
    LONG_SMA_PERIOD,
    RSI_COLUMN,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    RSI_PERIOD,
    SHORT_SMA_PERIOD,
    SMA_LONG_COLUMN,
    SMA_SHORT_COLUMN,
)

def create_candlestick_chart(
    df: pd.DataFrame,
    title: str = "Price Chart",
    show_sma50: bool = True,
    show_sma200: bool = True,
) -> go.Figure:
    """
    Builds a professional 3-panel chart:
    Panel 1: Candlesticks + configurable short/long SMAs
    Panel 2: Volume bars
    Panel 3: Configurable RSI with overbought/oversold levels
    """
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(
            f"{title} - Price & Moving Averages",
            "Trading Volume",
            f"Relative Strength Index (RSI {RSI_PERIOD})",
        ),
        row_heights=[0.58, 0.17, 0.25],
    )

    # 1. Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="OHLC",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350"
        ),
        row=1, col=1
    )

    # 2. Short moving average
    if show_sma50 and SMA_SHORT_COLUMN in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[SMA_SHORT_COLUMN],
                mode="lines",
                name=f"{SHORT_SMA_PERIOD}-Day SMA",
                line=dict(color="#f39c12", width=1.5)
            ),
            row=1, col=1
        )

    # 3. Long moving average
    if show_sma200 and SMA_LONG_COLUMN in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[SMA_LONG_COLUMN],
                mode="lines",
                name=f"{LONG_SMA_PERIOD}-Day SMA",
                line=dict(color="#9b59b6", width=1.5)
            ),
            row=1, col=1
        )

    # 4. Volume subplot
    if "Volume" in df.columns:
        volume_colors = [
            "#26a69a" if close >= open_price else "#ef5350"
            for open_price, close in zip(df["Open"], df["Close"])
        ]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                name="Volume",
                marker_color=volume_colors,
                opacity=0.65,
            ),
            row=2,
            col=1,
        )

    # 5. RSI Subplot
    if RSI_COLUMN in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[RSI_COLUMN],
                mode="lines",
                name=f"RSI {RSI_PERIOD}",
                line=dict(color="#29b6f6", width=1.5)
            ),
            row=3, col=1
        )

        # Overbought / Oversold threshold lines
        fig.add_hline(
            y=RSI_OVERBOUGHT,
            line_dash="dash",
            line_color="#ef5350",
            row=3,
            col=1,
            annotation_text=f"Overbought ({RSI_OVERBOUGHT:g})",
        )
        fig.add_hline(
            y=RSI_OVERSOLD,
            line_dash="dash",
            line_color="#26a69a",
            row=3,
            col=1,
            annotation_text=f"Oversold ({RSI_OVERSOLD:g})",
        )
        fig.update_yaxes(range=[0, 100], row=3, col=1)

    # Chart Styling
    fig.update_layout(
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        height=720,
        margin=dict(l=30, r=30, t=50, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode="x unified"
    )

    fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1)

    return fig
