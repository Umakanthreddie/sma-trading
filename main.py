"""
main.py — SMA Crossover Strategy Runner

Usage:
  python main.py                    Scan watchlist for signals
  python main.py --scan             Same as above
  python main.py --backtest         Run backtest on all watchlist tickers
  python main.py --plot TICKER      Generate chart for a specific ticker
  python main.py --plot-all         Generate charts for all watchlist tickers
  python main.py --add AAPL TSLA    Add tickers to watchlist (session only)
"""

import argparse
import sys

import config
import data_fetcher
import strategy
import alerts
import backtester
import plotter


def cmd_scan(tickers: list):
    """Scan all tickers and print BUY/SELL/HOLD signals."""
    alerts.print_scan_header(tickers)
    data   = data_fetcher.fetch_multiple(tickers)
    results = []

    for ticker, df in data.items():
        try:
            result = strategy.get_latest_signal(df, ticker=ticker)
            alerts.print_signal(result)
            results.append(result)
        except Exception as e:
            print(f"  ⚠️  Error analyzing {ticker}: {e}")

    alerts.print_scan_summary(results)

    # Send email if configured
    if config.EMAIL_ALERTS:
        alerts.send_email_alert(results)


def cmd_backtest(tickers: list):
    """Run strategy backtest on all tickers."""
    print(f"\n  🔬 Running backtests for: {', '.join(tickers)}\n")
    data = data_fetcher.fetch_multiple(tickers)
    backtester.run_all_backtests(data)


def cmd_plot(ticker: str):
    """Generate a strategy chart for a single ticker."""
    print(f"\n  📊 Generating chart for {ticker}...")
    try:
        df   = data_fetcher.fetch(ticker)
        path = plotter.plot_ticker(df, ticker)
        print(f"  ✅ Chart saved to: {path}\n")
    except Exception as e:
        print(f"  ❌ Failed to plot {ticker}: {e}\n")


def cmd_plot_all(tickers: list):
    """Generate strategy charts for all watchlist tickers."""
    print(f"\n  📊 Generating charts for all tickers...\n")
    data = data_fetcher.fetch_multiple(tickers)
    plotter.plot_all(data)
    print(f"\n  ✅ All charts saved to './{config.CHARTS_DIR}/' folder.\n")


def main():
    parser = argparse.ArgumentParser(
        description="SMA Crossover Trading Strategy — Signal Scanner & Backtester",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--scan",      action="store_true",  help="Scan watchlist for buy/sell signals (default)")
    parser.add_argument("--backtest",  action="store_true",  help="Run strategy backtest on watchlist")
    parser.add_argument("--plot",      metavar="TICKER",     help="Plot chart for a specific ticker")
    parser.add_argument("--plot-all",  action="store_true",  help="Plot charts for all watchlist tickers")
    parser.add_argument("--add",       metavar="TICKER", nargs="+", help="Add extra tickers to watchlist for this session")

    args = parser.parse_args()

    # Build effective watchlist
    tickers = list(config.WATCHLIST)
    if args.add:
        for t in args.add:
            t = t.upper()
            if t not in tickers:
                tickers.append(t)
        print(f"  ➕ Added to watchlist: {', '.join(args.add)}")

    # Route command
    if args.plot:
        cmd_plot(args.plot.upper())
    elif getattr(args, "plot_all", False):
        cmd_plot_all(tickers)
    elif args.backtest:
        cmd_backtest(tickers)
    else:
        # Default: scan
        cmd_scan(tickers)


if __name__ == "__main__":
    main()
