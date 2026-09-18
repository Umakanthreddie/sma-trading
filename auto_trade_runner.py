"""
auto_trade_runner.py — Headless auto-trade runner for scheduled/unattended runs.

This does exactly what the dashboard's "Run Auto-Trade Now" button does —
fetch data, analyze news, score with the AI predictor, and execute
buy/sell decisions through trader.auto_trade() — but from the command
line, so it can be triggered by Windows Task Scheduler on a recurring
basis (e.g. hourly during market hours) for the 2-week paper-trading test.

SAFETY:
  - Refuses to run at all unless config confirms this is paper trading
    (BROKER == "webull" and WEBULL_PAPER == True, or BROKER == "paper").
    This is a hard stop specifically so a scheduled/unattended task can
    never accidentally fire real-money trades — if you deliberately want
    to go live later, this script will tell you exactly what to change,
    but you must do that change yourself, deliberately, not while this
    script is running unattended.
  - Skips the run entirely outside US market hours (9:30–16:00 ET,
    Mon–Fri) unless --force is passed, to avoid wasted/failed API calls.
  - Every run appends one line to auto_trade_log.jsonl — a full audit
    trail of every decision and trade, timestamped, so nothing happens
    invisibly.

Usage:
  python auto_trade_runner.py            # normal scheduled run
  python auto_trade_runner.py --force    # ignore market-hours check (testing)
"""

import sys
import json
import traceback
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

import config
import data_fetcher
import news_analyzer
import ai_predictor
import trader
from risk_manager import RiskManager

LOG_FILE = "auto_trade_log.jsonl"


def log_event(event: dict):
    event["logged_at"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


def is_market_hours() -> bool:
    """True if it's currently a US market weekday, 9:30–16:00 ET."""
    if ZoneInfo is None:
        return True  # can't check — don't block the run
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:  # Sat/Sun
        return False
    open_t = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_t <= now <= close_t


def assert_paper_mode():
    """
    Hard safety gate. Refuses to run unattended unless trades are
    confirmed to land in a paper (fake-money) account: either the app's
    own internal simulator (BROKER == "paper"), or Webull's own
    paper-trading account (BROKER == "webull" and WEBULL_PAPER == True).
    If WEBULL_PAPER has been flipped to False, this stops immediately
    rather than ever placing an unattended real-money trade.
    """
    is_paper = (config.BROKER == "paper") or (
        config.BROKER == "webull" and config.WEBULL_PAPER
    )
    if not is_paper:
        print(
            "\n  🛑 REFUSING TO RUN: config is not set to paper trading.\n"
            f"     BROKER={config.BROKER!r}, WEBULL_PAPER={getattr(config, 'WEBULL_PAPER', None)!r}\n"
            "     This script will not place unattended trades that could touch\n"
            "     real money. If you intend to go live, do so manually and\n"
            "     deliberately from the dashboard, not from a scheduled task.\n"
        )
        sys.exit(1)


def run():
    assert_paper_mode()

    if "--force" not in sys.argv and not is_market_hours():
        print("  ⏸  Outside market hours (9:30–16:00 ET, Mon–Fri). Skipping run.")
        log_event({"event": "skipped", "reason": "outside_market_hours"})
        return

    tickers = list(getattr(config, "AUTO_TRADE_WATCHLIST", config.WATCHLIST))
    print(f"\n  🤖 Auto-trade run starting — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"     Mode: {'PAPER' if config.PAPER_TRADING else 'LIVE'} | Broker: {config.BROKER} | Tickers: {len(tickers)}")

    try:
        data_dict = data_fetcher.fetch_multiple(tickers)
        prices = {t: float(df["Close"].iloc[-1]) for t, df in data_dict.items() if not df.empty}
        news_dict = news_analyzer.analyze_multiple(tickers)
        preds = ai_predictor.predict_multiple(tickers, data_dict, news_dict)

        risk = RiskManager(config.PAPER_INITIAL_CAPITAL)
        results = trader.auto_trade(preds, prices, risk)

        portfolio = trader.get_portfolio_summary(prices)

        # Surface broker connection problems loudly instead of silently
        # showing $0 — a $0 paper portfolio almost always means the
        # Webull login/session failed, not that the account is empty.
        if "Error" in portfolio.get("mode", "") or portfolio.get("error"):
            print(f"     ⚠️  Webull connection problem: {portfolio.get('mode')} — {portfolio.get('error', 'no details')}")

        log_event({
            "event": "run_complete",
            "predictions": [
                {"ticker": p["ticker"], "ai_score": p["ai_score"], "recommendation": p["recommendation"]}
                for p in preds
            ],
            "trades": results,
            "portfolio_value": portfolio.get("total_value"),
            "total_pnl": portfolio.get("total_pnl"),
            "total_pnl_pct": portfolio.get("total_pnl_pct"),
            "open_positions": len(portfolio.get("positions", [])),
            "broker_mode": portfolio.get("mode"),
            "broker_error": portfolio.get("error"),
        })

        if results:
            for r in results:
                if r.get("success"):
                    print(f"     ✅ {r.get('action')} {r.get('ticker')} — {r}")
                else:
                    print(f"     ⚠️  {r.get('ticker')}: {r.get('reason')}")
        else:
            print("     No trades executed this run — no signal met all criteria.")

        print(f"     Portfolio value: ${portfolio.get('total_value', 0):,.2f} "
              f"(P&L: {portfolio.get('total_pnl_pct', 0):+.2f}%)")
        print(f"  ✅ Run complete. Logged to {LOG_FILE}\n")

    except Exception as e:
        print(f"  ❌ Run failed: {e}")
        log_event({"event": "error", "error": str(e), "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    run()
