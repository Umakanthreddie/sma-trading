"""
data_fetcher.py — Fetch and cache historical stock price data using yfinance.
"""

import os
import pickle
import hashlib
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd

import config


def _cache_path(ticker: str, days: int) -> str:
    """Generate a cache file path for a ticker/days combo."""
    os.makedirs(config.DATA_CACHE_DIR, exist_ok=True)
    key = hashlib.md5(f"{ticker}_{days}".encode()).hexdigest()
    return os.path.join(config.DATA_CACHE_DIR, f"{ticker}_{key}.pkl")


def fetch(ticker: str, days: int = config.LOOKBACK_DAYS, use_cache: bool = True) -> pd.DataFrame:
    """
    Fetch historical OHLCV data for a ticker.

    Args:
        ticker:     Stock symbol (e.g. "AAPL")
        days:       Number of calendar days of history to fetch
        use_cache:  If True, return cached data if it's less than 1 hour old

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
        Index: DatetimeIndex (UTC)
    """
    cache_file = _cache_path(ticker, days)

    # Return cache if fresh (< 1 hour old)
    if use_cache and os.path.exists(cache_file):
        age_seconds = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))).total_seconds()
        if age_seconds < 3600:
            with open(cache_file, "rb") as f:
                return pickle.load(f)

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=days)

    try:
        df = yf.download(
            ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
        )
    except Exception as e:
        raise RuntimeError(f"Failed to fetch data for {ticker}: {e}")

    if df.empty:
        raise ValueError(f"No data returned for ticker '{ticker}'. Check the symbol.")

    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Cache result
    with open(cache_file, "wb") as f:
        pickle.dump(df, f)

    return df


def fetch_multiple(tickers: list, days: int = config.LOOKBACK_DAYS) -> dict:
    """
    Fetch data for multiple tickers.

    Returns:
        Dict mapping ticker -> DataFrame (skips tickers that fail)
    """
    results = {}
    for ticker in tickers:
        try:
            results[ticker] = fetch(ticker, days)
        except Exception as e:
            print(f"  ⚠️  Skipping {ticker}: {e}")
    return results
