"""
plotter.py — Chart generator for SMA crossover strategy.

Generates a matplotlib chart per ticker showing:
  - Closing price
  - SMA-short and SMA-long lines
  - Buy (▲) and Sell (▼) signal markers
"""

import os
import matplotlib
matplotlib.use("Agg")   # Non-interactive backend (saves to file)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

import strategy
import config


def plot_ticker(df: pd.DataFrame, ticker: str,
                short: int = config.SMA_SHORT, long: int = config.SMA_LONG,
                show: bool = False) -> str:
    """
    Generate and save a chart for one ticker.

    Args:
        df:     OHLCV DataFrame
        ticker: Stock symbol (used in title and filename)
        short:  Short SMA period
        long:   Long SMA period
        show:   If True, display interactively (requires GUI). Otherwise save to file.

    Returns:
        Path to saved chart file.
    """
    df = strategy.detect_signals(df, short, long)
    short_col = f"SMA_{short}"
    long_col  = f"SMA_{long}"

    df = df.dropna(subset=[short_col, long_col])

    buys  = df[df["Signal"] == strategy.SIGNAL_BUY]
    sells = df[df["Signal"] == strategy.SIGNAL_SELL]

    # ── Figure layout ────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 8),
        gridspec_kw={"height_ratios": [3, 1]},
        sharex=True
    )
    fig.patch.set_facecolor("#0f1117")
    for ax in (ax1, ax2):
        ax.set_facecolor("#1a1d2e")
        ax.tick_params(colors="#cccccc")
        ax.spines["bottom"].set_color("#333355")
        ax.spines["top"].set_color("#333355")
        ax.spines["left"].set_color("#333355")
        ax.spines["right"].set_color("#333355")

    # ── Price + SMAs ─────────────────────────────────────────
    ax1.plot(df.index, df["Close"],       color="#4fc3f7", linewidth=1.4, label="Close Price", zorder=2)
    ax1.plot(df.index, df[short_col],     color="#ffb300", linewidth=1.2, linestyle="--", label=f"SMA-{short}", zorder=3)
    ax1.plot(df.index, df[long_col],      color="#ef5350", linewidth=1.2, linestyle="--", label=f"SMA-{long}", zorder=3)

    # ── Buy / Sell markers ───────────────────────────────────
    if not buys.empty:
        ax1.scatter(
            buys.index, buys["Close"],
            marker="^", color="#00e676", s=120, zorder=5, label="BUY (Golden Cross)"
        )
    if not sells.empty:
        ax1.scatter(
            sells.index, sells["Close"],
            marker="v", color="#ff5252", s=120, zorder=5, label="SELL (Death Cross)"
        )

    # ── Shaded regions ───────────────────────────────────────
    ax1.fill_between(
        df.index,
        df[short_col], df[long_col],
        where=df[short_col] >= df[long_col],
        alpha=0.08, color="#00e676", label="_nolegend_"
    )
    ax1.fill_between(
        df.index,
        df[short_col], df[long_col],
        where=df[short_col] < df[long_col],
        alpha=0.08, color="#ff5252", label="_nolegend_"
    )

    ax1.set_title(
        f"{ticker}  —  SMA-{short} / SMA-{long} Crossover Strategy",
        color="white", fontsize=14, fontweight="bold", pad=12
    )
    ax1.set_ylabel("Price (USD)", color="#aaaaaa")
    ax1.yaxis.label.set_color("#aaaaaa")
    ax1.tick_params(axis="y", colors="#aaaaaa")
    ax1.legend(facecolor="#1a1d2e", edgecolor="#333355", labelcolor="white", fontsize=9)
    ax1.grid(alpha=0.15, color="#333355")

    # ── Signal Strength (MA gap %) ───────────────────────────
    ax2.fill_between(
        df.index, df["Signal_Strength"],
        where=df["Position"] == 1,
        color="#00e676", alpha=0.5, label="Bullish gap"
    )
    ax2.fill_between(
        df.index, df["Signal_Strength"],
        where=df["Position"] == -1,
        color="#ff5252", alpha=0.5, label="Bearish gap"
    )
    ax2.set_ylabel("MA Gap %", color="#aaaaaa")
    ax2.yaxis.label.set_color("#aaaaaa")
    ax2.tick_params(axis="y", colors="#aaaaaa")
    ax2.legend(facecolor="#1a1d2e", edgecolor="#333355", labelcolor="white", fontsize=8)
    ax2.grid(alpha=0.15, color="#333355")

    # ── X-axis formatting ────────────────────────────────────
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.xticks(rotation=30, color="#aaaaaa")
    plt.xlabel("Date", color="#aaaaaa")

    plt.tight_layout(pad=1.5)

    # ── Save ─────────────────────────────────────────────────
    os.makedirs(config.CHARTS_DIR, exist_ok=True)
    out_path = os.path.join(config.CHARTS_DIR, f"{ticker}_SMA{short}_{long}.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return out_path


def plot_all(data_dict: dict, **kwargs):
    """
    Generate charts for all tickers in data_dict.

    Args:
        data_dict: Dict of {ticker: DataFrame}
        kwargs:    Passed to plot_ticker()
    """
    paths = []
    for ticker, df in data_dict.items():
        try:
            path = plot_ticker(df, ticker, **kwargs)
            print(f"  📊 Chart saved: {path}")
            paths.append(path)
        except Exception as e:
            print(f"  ⚠️  Failed to plot {ticker}: {e}")
    return paths
