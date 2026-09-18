"""
alerts.py — Console and email alert system for SMA signals.
"""

import smtplib
import os
import sys
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Force UTF-8 output on Windows to avoid cp1252 encoding errors
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

import config


# ─────────────────────────────────────────────
# Color helpers
# ─────────────────────────────────────────────

def _green(text):  return (Fore.GREEN  + str(text) + Style.RESET_ALL) if HAS_COLOR else str(text)
def _red(text):    return (Fore.RED    + str(text) + Style.RESET_ALL) if HAS_COLOR else str(text)
def _yellow(text): return (Fore.YELLOW + str(text) + Style.RESET_ALL) if HAS_COLOR else str(text)
def _cyan(text):   return (Fore.CYAN   + str(text) + Style.RESET_ALL) if HAS_COLOR else str(text)
def _bold(text):   return (Style.BRIGHT + str(text) + Style.RESET_ALL) if HAS_COLOR else str(text)


# ─────────────────────────────────────────────
# Console Alert
# ─────────────────────────────────────────────

def print_signal(result: dict):
    """
    Print a color-coded signal alert to the console.

    Args:
        result: Dict returned by strategy.get_latest_signal()
    """
    sig   = result["signal"]
    tk    = result["ticker"]
    date  = result["date"]
    close = result["close"]
    ss    = result["sma_short"]
    sl    = result["sma_long"]
    strength = result["signal_strength"]
    pos   = result["position_status"]

    if sig == "BUY":
        icon  = "🟢"
        label = _green(_bold("  BUY  "))
        color = _green
    elif sig == "SELL":
        icon  = "🔴"
        label = _red(_bold("  SELL "))
        color = _red
    else:
        icon  = "🟡"
        label = _yellow(_bold("  HOLD "))
        color = _yellow

    print(f"\n{'─'*58}")
    print(f"  {icon} {_bold(tk):<8}  {label}   {_cyan(date)}")
    print(f"{'─'*58}")
    print(f"  Price       : {color(f'${close:,.2f}')}")
    print(f"  SMA-{config.SMA_SHORT:<2}       : ${ss:,.2f}")
    print(f"  SMA-{config.SMA_LONG:<2}       : ${sl:,.2f}")
    print(f"  MA Gap      : {strength:.3f}%")
    print(f"  Trend       : {pos}")
    print(f"{'─'*58}")


def print_scan_header(tickers: list):
    print(f"\n{'═'*58}")
    print(f"  📊 SMA Crossover Scan  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Watchlist: {', '.join(tickers)}")
    print(f"  Strategy : SMA-{config.SMA_SHORT} / SMA-{config.SMA_LONG}")
    print(f"{'═'*58}")


def print_scan_summary(signals: list):
    buys  = [s["ticker"] for s in signals if s["signal"] == "BUY"]
    sells = [s["ticker"] for s in signals if s["signal"] == "SELL"]
    holds = [s["ticker"] for s in signals if s["signal"] == "HOLD"]

    print(f"\n{'═'*58}")
    print(f"  📋 SCAN SUMMARY")
    print(f"{'─'*58}")
    if buys:
        print(f"  🟢 BUY  signals : {', '.join(buys)}")
    if sells:
        print(f"  🔴 SELL signals : {', '.join(sells)}")
    if holds:
        print(f"  🟡 HOLD         : {', '.join(holds)}")
    print(f"{'═'*58}\n")

    if buys or sells:
        print("  ⚠️  DISCLAIMER: These are algorithmic signals, NOT financial advice.")
        print("      Always do your own research before trading.\n")


# ─────────────────────────────────────────────
# Email Alert
# ─────────────────────────────────────────────

def _build_email_body(signals: list) -> str:
    lines = [f"SMA Crossover Scan — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    lines.append(f"Strategy: SMA-{config.SMA_SHORT} / SMA-{config.SMA_LONG}\n")
    lines.append("=" * 50)

    for r in signals:
        sig = r["signal"]
        if sig == "HOLD":
            continue
        lines.append(
            f"\n[{sig}] {r['ticker']}\n"
            f"  Date     : {r['date']}\n"
            f"  Price    : ${r['close']:,.2f}\n"
            f"  SMA-{config.SMA_SHORT}  : ${r['sma_short']:,.2f}\n"
            f"  SMA-{config.SMA_LONG}  : ${r['sma_long']:,.2f}\n"
            f"  MA Gap   : {r['signal_strength']:.3f}%\n"
            f"  Trend    : {r['position_status']}\n"
        )

    lines.append("\n" + "=" * 50)
    lines.append("\n⚠️ DISCLAIMER: Algorithmic signals only — not financial advice.")
    return "\n".join(lines)


def send_email_alert(signals: list):
    """Send email summary of all BUY/SELL signals."""
    actionable = [s for s in signals if s["signal"] != "HOLD"]
    if not actionable:
        return  # Nothing to email

    body = _build_email_body(signals)
    subject = f"📈 SMA Alert: {', '.join([s['ticker'] for s in actionable])} — {datetime.now().strftime('%Y-%m-%d')}"

    msg = MIMEMultipart()
    msg["From"]    = config.EMAIL_SENDER
    msg["To"]      = config.EMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            server.sendmail(config.EMAIL_SENDER, config.EMAIL_RECEIVER, msg.as_string())
        print(f"  ✅ Email alert sent to {config.EMAIL_RECEIVER}")
    except Exception as e:
        print(f"  ❌ Failed to send email: {e}")
