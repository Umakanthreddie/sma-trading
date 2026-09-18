"""
strategy.py — SMA Crossover Strategy Engine.

Logic:
  - Computes SMA_short and SMA_long on closing prices.
  - BUY  signal: SMA_short crosses ABOVE SMA_long  (Golden Cross)
  - SELL signal: SMA_short crosses BELOW SMA_long  (Death Cross)
  - HOLD: no crossover detected today
"""

import pandas as pd
import numpy as np
import config


SIGNAL_BUY  = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"


def compute_smas(df: pd.DataFrame, short: int = config.SMA_SHORT, long: int = config.SMA_LONG) -> pd.DataFrame:
    """
    Add SMA columns to the dataframe.

    Args:
        df:     OHLCV DataFrame (must have 'Close' column)
        short:  Short SMA period
        long:   Long SMA period

    Returns:
        DataFrame with additional columns: SMA_short, SMA_long
    """
    df = df.copy()
    df[f"SMA_{short}"] = df["Close"].rolling(window=short).mean()
    df[f"SMA_{long}"]  = df["Close"].rolling(window=long).mean()
    return df


def detect_signals(df: pd.DataFrame, short: int = config.SMA_SHORT, long: int = config.SMA_LONG) -> pd.DataFrame:
    """
    Detect BUY/SELL/HOLD crossover signals across all rows.

    Returns:
        DataFrame with additional columns:
          - Signal:          "BUY" | "SELL" | "HOLD"
          - Signal_Strength: % gap between SMAs (higher = stronger signal)
          - Position:        1 (above) or -1 (below) or 0 (undefined)
    """
    df = compute_smas(df, short, long)
    short_col = f"SMA_{short}"
    long_col  = f"SMA_{long}"

    # Position: 1 when short > long, -1 when short < long
    df["Position"] = np.where(df[short_col] > df[long_col], 1, -1)
    df["Position"] = np.where(df[[short_col, long_col]].isna().any(axis=1), 0, df["Position"])

    # Crossover: position changed from previous day
    df["Crossover"] = df["Position"].diff()

    # Signal strength: % difference between SMAs
    df["Signal_Strength"] = ((df[short_col] - df[long_col]) / df[long_col] * 100).abs().round(3)

    # Assign signals
    conditions = [
        (df["Crossover"] > 0) & (df["Signal_Strength"] >= config.MIN_SIGNAL_STRENGTH),  # BUY
        (df["Crossover"] < 0) & (df["Signal_Strength"] >= config.MIN_SIGNAL_STRENGTH),  # SELL
    ]
    df["Signal"] = np.select(conditions, [SIGNAL_BUY, SIGNAL_SELL], default=SIGNAL_HOLD)

    return df


def get_latest_signal(df: pd.DataFrame, ticker: str = "",
                      short: int = config.SMA_SHORT, long: int = config.SMA_LONG) -> dict:
    """
    Get the most recent signal for a stock.

    Returns a dict with:
      ticker, date, close, sma_short, sma_long, signal, signal_strength, position_status
    """
    df = detect_signals(df, short, long)
    short_col = f"SMA_{short}"
    long_col  = f"SMA_{long}"

    last = df.dropna(subset=[short_col, long_col]).iloc[-1]

    # Current positional status (regardless of crossover today)
    if last["Position"] == 1:
        pos_status = f"Short MA above Long MA (Bullish)"
    elif last["Position"] == -1:
        pos_status = f"Short MA below Long MA (Bearish)"
    else:
        pos_status = "Insufficient data"

    return {
        "ticker":           ticker,
        "date":             str(last.name.date()),
        "close":            round(float(last["Close"]), 2),
        "sma_short":        round(float(last[short_col]), 2),
        "sma_long":         round(float(last[long_col]), 2),
        "signal":           last["Signal"],
        "signal_strength":  round(float(last["Signal_Strength"]), 3),
        "position_status":  pos_status,
    }


def get_all_signals(df: pd.DataFrame, short: int = config.SMA_SHORT, long: int = config.SMA_LONG) -> pd.DataFrame:
    """
    Return all historical BUY/SELL signals (not HOLDs) in the dataset.

    Useful for backtesting and charting signal markers.
    """
    df = detect_signals(df, short, long)
    return df[df["Signal"] != SIGNAL_HOLD].copy()
