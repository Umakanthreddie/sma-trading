"""
backtester.py — Simulates the SMA crossover strategy on historical data.

Tracks:
  - Entry (BUY) and Exit (SELL) trades
  - Per-trade P&L and % return
  - Win rate, total return, max drawdown
"""

import pandas as pd
import numpy as np
from tabulate import tabulate

import strategy
import config


def run_backtest(df: pd.DataFrame, ticker: str = "",
                 short: int = config.SMA_SHORT, long: int = config.SMA_LONG,
                 initial_capital: float = 10_000.0) -> dict:
    """
    Simulate the SMA crossover strategy on historical data.

    Args:
        df:               OHLCV DataFrame
        ticker:           Stock symbol (for display)
        short:            Short SMA period
        long:             Long SMA period
        initial_capital:  Starting cash (USD)

    Returns:
        Dict containing:
          - trades:         List of completed trade dicts
          - metrics:        Summary metrics dict
          - equity_curve:   Series of portfolio value over time
    """
    df = strategy.detect_signals(df, short, long)
    short_col = f"SMA_{short}"
    long_col  = f"SMA_{long}"

    # Drop rows where SMAs aren't ready yet
    df = df.dropna(subset=[short_col, long_col]).copy()

    trades      = []
    in_trade    = False
    entry_price = 0.0
    entry_date  = None
    shares      = 0

    cash   = initial_capital
    equity = []

    for idx, row in df.iterrows():
        price = float(row["Close"])
        sig   = row["Signal"]

        # BUY — enter trade
        if sig == strategy.SIGNAL_BUY and not in_trade:
            shares      = cash // price
            cost        = shares * price
            cash       -= cost
            in_trade    = True
            entry_price = price
            entry_date  = idx

        # SELL — exit trade
        elif sig == strategy.SIGNAL_SELL and in_trade:
            proceeds    = shares * price
            cash       += proceeds
            pnl         = proceeds - (shares * entry_price)
            pct_return  = (price - entry_price) / entry_price * 100
            trades.append({
                "Ticker":     ticker,
                "Entry Date": str(entry_date.date()),
                "Exit Date":  str(idx.date()),
                "Entry $":    round(entry_price, 2),
                "Exit $":     round(price, 2),
                "Shares":     int(shares),
                "P&L $":      round(pnl, 2),
                "Return %":   round(pct_return, 2),
                "Result":     "WIN ✅" if pnl > 0 else "LOSS ❌",
            })
            in_trade = False
            shares   = 0

        # Track portfolio value
        portfolio_value = cash + (shares * price if in_trade else 0)
        equity.append({"Date": idx, "Value": portfolio_value})

    # Close any open trade at last price
    if in_trade:
        last_price = float(df["Close"].iloc[-1])
        open_value = shares * last_price
        equity[-1]["Value"] = cash + open_value

    equity_series = pd.DataFrame(equity).set_index("Date")["Value"] if equity else pd.Series()
    final_value   = float(equity_series.iloc[-1]) if len(equity_series) else initial_capital

    # Metrics
    total_return_pct  = (final_value - initial_capital) / initial_capital * 100
    wins              = [t for t in trades if t["P&L $"] > 0]
    losses            = [t for t in trades if t["P&L $"] <= 0]
    win_rate          = len(wins) / len(trades) * 100 if trades else 0.0

    # Max Drawdown
    if len(equity_series) > 1:
        roll_max  = equity_series.cummax()
        drawdown  = (equity_series - roll_max) / roll_max * 100
        max_dd    = round(float(drawdown.min()), 2)
    else:
        max_dd = 0.0

    metrics = {
        "Ticker":           ticker,
        "Initial Capital":  f"${initial_capital:,.2f}",
        "Final Value":      f"${final_value:,.2f}",
        "Total Return":     f"{total_return_pct:+.2f}%",
        "Total Trades":     len(trades),
        "Wins":             len(wins),
        "Losses":           len(losses),
        "Win Rate":         f"{win_rate:.1f}%",
        "Max Drawdown":     f"{max_dd:.2f}%",
    }

    return {
        "ticker":       ticker,
        "trades":       trades,
        "metrics":      metrics,
        "equity_curve": equity_series,
    }


def print_backtest_results(result: dict):
    """Pretty-print backtest trades and metrics."""
    ticker  = result["ticker"]
    trades  = result["trades"]
    metrics = result["metrics"]

    print(f"\n{'═'*70}")
    print(f"  📈 BACKTEST RESULTS — {ticker}")
    print(f"  Strategy: SMA-{config.SMA_SHORT} / SMA-{config.SMA_LONG}")
    print(f"{'═'*70}")

    if trades:
        print("\n  📋 Trade History:")
        headers = ["Entry Date", "Exit Date", "Entry $", "Exit $", "Shares", "P&L $", "Return %", "Result"]
        rows = [[t[h] for h in headers] for t in trades]
        print(tabulate(rows, headers=headers, tablefmt="rounded_outline", floatfmt=".2f"))
    else:
        print("\n  No completed trades in this period.")

    print(f"\n  📊 Summary Metrics:")
    for k, v in metrics.items():
        if k != "Ticker":
            print(f"    {k:<20}: {v}")

    print(f"\n{'═'*70}\n")
    print("  ⚠️  Backtest results are based on historical data and past performance")
    print("      does not guarantee future results. Not financial advice.\n")


def run_all_backtests(data_dict: dict, **kwargs) -> list:
    """
    Run backtests for all tickers in a data dict.

    Args:
        data_dict: Dict of {ticker: DataFrame} from data_fetcher.fetch_multiple()
        kwargs:    Passed to run_backtest()

    Returns:
        List of backtest result dicts
    """
    results = []
    for ticker, df in data_dict.items():
        try:
            result = run_backtest(df, ticker=ticker, **kwargs)
            print_backtest_results(result)
            results.append(result)
        except Exception as e:
            print(f"  ⚠️  Backtest failed for {ticker}: {e}")
    return results
