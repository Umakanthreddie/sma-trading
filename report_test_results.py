"""
report_test_results.py — Summarize the paper-trading test so far.

Reads auto_trade_log.jsonl (written by auto_trade_runner.py) and prints
a plain-English summary: how many runs, how many trades, win rate,
current portfolio value and P&L.

Usage:
  python report_test_results.py
"""

import json
import os
from collections import Counter

LOG_FILE = "auto_trade_log.jsonl"


def main():
    if not os.path.exists(LOG_FILE):
        print(f"No {LOG_FILE} found yet — the runner hasn't logged anything.")
        return

    runs = []
    with open(LOG_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                runs.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    completed = [r for r in runs if r.get("event") == "run_complete"]
    skipped = [r for r in runs if r.get("event") == "skipped"]
    errors = [r for r in runs if r.get("event") == "error"]

    all_trades = []
    for r in completed:
        all_trades.extend(r.get("trades", []))

    executed = [t for t in all_trades if t.get("success")]
    buys = [t for t in executed if t.get("action") == "BUY"]
    sells = [t for t in executed if t.get("action") == "SELL"]
    wins = [t for t in sells if t.get("pnl", 0) > 0]
    losses = [t for t in sells if t.get("pnl", 0) <= 0]

    print("\n📊  PAPER TRADING TEST SUMMARY")
    print("─" * 45)
    print(f"Total scheduled runs logged : {len(runs)}")
    print(f"  Completed runs           : {len(completed)}")
    print(f"  Skipped (off-hours)      : {len(skipped)}")
    print(f"  Errors                   : {len(errors)}")
    print()
    print(f"Trades executed            : {len(executed)}  (BUY: {len(buys)}, SELL: {len(sells)})")
    if sells:
        win_rate = len(wins) / len(sells) * 100
        print(f"Closed positions          : {len(sells)}")
        print(f"  Winners / Losers         : {len(wins)} / {len(losses)}")
        print(f"  Win rate                 : {win_rate:.1f}%")
        total_pnl = sum(t.get("pnl", 0) for t in sells)
        print(f"  Realized P&L (closed)    : ${total_pnl:+,.2f}")

    if completed:
        latest = completed[-1]
        print()
        print(f"Latest portfolio value     : ${latest.get('portfolio_value', 0):,.2f}")
        print(f"Latest total P&L           : ${latest.get('total_pnl', 0):+,.2f} "
              f"({latest.get('total_pnl_pct', 0):+.2f}%)")
        print(f"Open positions             : {latest.get('open_positions', 0)}")

    if errors:
        print("\n⚠️  Recent errors:")
        for e in errors[-3:]:
            print(f"  - {e.get('logged_at')}: {e.get('error')}")

    print()


if __name__ == "__main__":
    main()
