"""
trader.py — Multi-broker trading engine.

BROKER = "paper"     → Internal paper trading (safe, no account needed)
BROKER = "webull"    → Webull paper or live trading
BROKER = "robinhood" → Robinhood live trading
"""

import json
import os
from datetime import datetime

import config
from risk_manager import RiskManager

# ─────────────────────────────────────────────
# State persistence (JSON file)
# ─────────────────────────────────────────────
STATE_FILE = "paper_portfolio.json"

_DEFAULT_STATE = {
    "cash":       config.PAPER_INITIAL_CAPITAL,
    "positions":  {},      # {ticker: {shares, entry_price, entry_date, cost}}
    "trade_log":  [],      # list of trade dicts
    "day_start":  config.PAPER_INITIAL_CAPITAL,
}


def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(_DEFAULT_STATE)


def _save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ─────────────────────────────────────────────
# Portfolio value
# ─────────────────────────────────────────────
def portfolio_value(prices: dict = None) -> float:
    """
    Current total portfolio value (cash + open positions at market price).

    Args:
        prices: Dict {ticker: current_price}. Fetched if not provided.
    """
    state = _load_state()
    total = state["cash"]
    for ticker, pos in state["positions"].items():
        price = prices.get(ticker, pos["entry_price"]) if prices else pos["entry_price"]
        total += pos["shares"] * price
    return round(total, 2)


# ─────────────────────────────────────────────
# Paper Trading
# ─────────────────────────────────────────────

def paper_buy(ticker: str, current_price: float,
              ai_score: float, reason: str,
              risk: RiskManager) -> dict:
    """
    Simulate buying a stock (paper trade).

    Returns:
        Trade result dict
    """
    state = _load_state()
    prices = {t: p["entry_price"] for t, p in state["positions"].items()}
    pv = portfolio_value(prices)

    # Risk check
    allowed, msg = risk.can_buy(ticker, ai_score, pv, state["positions"])
    if not allowed:
        return {"success": False, "reason": msg, "ticker": ticker, "action": "BUY"}

    # Position size
    shares = risk.position_size(pv, current_price)
    if shares <= 0:
        return {"success": False, "reason": "Not enough cash for even 1 share", "ticker": ticker, "action": "BUY"}

    cost = shares * current_price
    if cost > state["cash"]:
        shares = int(state["cash"] // current_price)
        if shares <= 0:
            return {"success": False, "reason": "Insufficient cash", "ticker": ticker, "action": "BUY"}
        cost = shares * current_price

    # Execute
    state["cash"] -= cost
    state["positions"][ticker] = {
        "shares":      shares,
        "entry_price": current_price,
        "entry_date":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "cost":        cost,
    }

    trade = {
        "action":    "BUY",
        "ticker":    ticker,
        "shares":    shares,
        "price":     current_price,
        "cost":      round(cost, 2),
        "ai_score":  ai_score,
        "reason":    reason,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode":      "PAPER",
    }
    state["trade_log"].append(trade)
    _save_state(state)

    return {"success": True, **trade}


def paper_sell(ticker: str, current_price: float,
               reason: str) -> dict:
    """
    Simulate selling a stock position (paper trade).
    """
    state = _load_state()
    if ticker not in state["positions"]:
        return {"success": False, "reason": f"No position in {ticker}", "ticker": ticker, "action": "SELL"}

    pos      = state["positions"][ticker]
    proceeds = pos["shares"] * current_price
    pnl      = proceeds - pos["cost"]
    pnl_pct  = pnl / pos["cost"] * 100

    state["cash"] += proceeds
    del state["positions"][ticker]

    trade = {
        "action":       "SELL",
        "ticker":       ticker,
        "shares":       pos["shares"],
        "entry_price":  pos["entry_price"],
        "exit_price":   current_price,
        "proceeds":     round(proceeds, 2),
        "pnl":          round(pnl, 2),
        "pnl_pct":      round(pnl_pct, 2),
        "reason":       reason,
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode":         "PAPER",
    }
    state["trade_log"].append(trade)
    _save_state(state)

    return {"success": True, **trade}


# ─────────────────────────────────────────────
# Live Robinhood Trading
# ─────────────────────────────────────────────

def _get_robinhood():
    """Load robin_stocks and login (lazy)."""
    try:
        import robin_stocks.robinhood as rh
        rh.login(
            username=config.ROBINHOOD_USERNAME,
            password=config.ROBINHOOD_PASSWORD,
            expiresIn=86400,
            store_session=True,
        )
        return rh
    except ImportError:
        raise RuntimeError("robin_stocks not installed. Run: pip install robin_stocks")
    except Exception as e:
        raise RuntimeError(f"Robinhood login failed: {e}")


def live_buy(ticker: str, current_price: float,
             ai_score: float, reason: str,
             risk: RiskManager, shares: int = None) -> dict:
    """Place a real buy order on Robinhood."""
    rh = _get_robinhood()

    portfolio = rh.build_holdings()
    cash_info = rh.load_account_profile()
    cash      = float(cash_info.get("portfolio_cash", 0))
    positions = {k: v for k, v in portfolio.items()}

    allowed, msg = risk.can_buy(ticker, ai_score, cash, positions)
    if not allowed:
        return {"success": False, "reason": msg, "ticker": ticker, "action": "BUY"}

    if shares is None:
        shares = risk.position_size(cash, current_price)

    if shares <= 0:
        return {"success": False, "reason": "Shares = 0", "ticker": ticker, "action": "BUY"}

    try:
        order = rh.order_buy_market(ticker, shares)
        trade = {
            "action":    "BUY",
            "ticker":    ticker,
            "shares":    shares,
            "price":     current_price,
            "ai_score":  ai_score,
            "reason":    reason,
            "order_id":  order.get("id", ""),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode":      "LIVE",
        }
        # Also log to paper state for tracking
        state = _load_state()
        state["trade_log"].append(trade)
        _save_state(state)
        return {"success": True, **trade}
    except Exception as e:
        return {"success": False, "reason": str(e), "ticker": ticker, "action": "BUY"}


def live_sell(ticker: str, reason: str) -> dict:
    """Sell all shares of a stock on Robinhood."""
    rh = _get_robinhood()
    try:
        holdings = rh.build_holdings()
        if ticker not in holdings:
            return {"success": False, "reason": f"No Robinhood position in {ticker}"}
        shares = int(float(holdings[ticker]["quantity"]))
        order  = rh.order_sell_market(ticker, shares)
        trade  = {
            "action":    "SELL",
            "ticker":    ticker,
            "shares":    shares,
            "reason":    reason,
            "order_id":  order.get("id", ""),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode":      "LIVE",
        }
        state = _load_state()
        state["trade_log"].append(trade)
        _save_state(state)
        return {"success": True, **trade}
    except Exception as e:
        return {"success": False, "reason": str(e), "ticker": ticker, "action": "SELL"}



# ─────────────────────────────────────────────
# Broker router helpers
# ─────────────────────────────────────────────

def _execute_buy(ticker, price, ai_score, reason, risk):
    broker = config.BROKER.lower()
    if broker == "webull":
        import webull_broker as wb
        # Risk check (use paper state for position tracking)
        state = _load_state()
        pv = portfolio_value({t: p["entry_price"] for t, p in state["positions"].items()})
        allowed, msg = risk.can_buy(ticker, ai_score, pv, state["positions"])
        if not allowed:
            return {"success": False, "reason": msg, "ticker": ticker, "action": "BUY"}
        shares = risk.position_size(pv, price)
        result = wb.buy(ticker, shares, ai_score, reason)
        # Log to local trade log
        if result.get("success"):
            state["positions"][ticker] = {
                "shares": shares, "entry_price": price,
                "entry_date": datetime.now().strftime("%Y-%m-%d %H:%M"), "cost": shares * price,
            }
            state["trade_log"].append({**result, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            _save_state(state)
        return result
    elif broker == "robinhood":
        return live_buy(ticker, price, ai_score, reason, risk)
    else:
        return paper_buy(ticker, price, ai_score, reason, risk)


def _execute_sell(ticker, price, reason):
    broker = config.BROKER.lower()
    if broker == "webull":
        import webull_broker as wb
        result = wb.sell(ticker, reason)
        if result.get("success"):
            state = _load_state()
            pos = state["positions"].pop(ticker, {})
            pnl = (price - pos.get("entry_price", price)) * pos.get("shares", 0)
            result["pnl"] = round(pnl, 2)
            state["trade_log"].append({**result, "exit_price": price, "pnl": round(pnl, 2),
                                       "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            _save_state(state)
        return result
    elif broker == "robinhood":
        return live_sell(ticker, reason)
    else:
        return paper_sell(ticker, price, reason)


# ─────────────────────────────────────────────
# Auto-Trade Runner (called by dashboard)
# ─────────────────────────────────────────────

def auto_trade(predictions: list, prices: dict, risk: RiskManager) -> list:
    """
    Automatically execute trades based on AI predictions.
    Routes to the correct broker based on config.BROKER.

    Args:
        predictions: List of dicts from ai_predictor.predict_multiple()
        prices:      Dict {ticker: current_price}
        risk:        RiskManager instance

    Returns:
        List of executed trade results
    """
    state   = _load_state()
    results = []
    risk.reset_daily(portfolio_value(prices))

    for pred in predictions:
        ticker   = pred["ticker"]
        ai_score = pred["ai_score"]
        rec      = pred["recommendation"]
        price    = prices.get(ticker, 0)
        if price <= 0:
            continue

        # Stop-loss check on tracked positions
        if ticker in state["positions"]:
            pos = state["positions"][ticker]
            if risk.should_stop_loss(ticker, pos["entry_price"], price):
                reason = f"Stop-loss: entry=${pos['entry_price']:.2f}, now=${price:.2f}"
                result = _execute_sell(ticker, price, reason)
                results.append(result)
                state = _load_state()
                continue

        # BUY
        if "BUY" in rec and ticker not in state["positions"]:
            reason = f"AI {ai_score:.0f}/100 | {pred['sentiment_label']} | {rec}"
            result = _execute_buy(ticker, price, ai_score, reason, risk)
            results.append(result)
            state = _load_state()

        # SELL
        elif "SELL" in rec and ticker in state["positions"]:
            reason = f"AI {ai_score:.0f}/100 | {pred['sentiment_label']} | {rec}"
            result = _execute_sell(ticker, price, reason)
            results.append(result)
            state = _load_state()

    return results


def get_portfolio_summary(prices: dict = None) -> dict:
    """
    Get portfolio state — from broker if Webull, otherwise from local paper state.
    """
    broker = config.BROKER.lower()

    if broker == "webull":
        try:
            import webull_broker as wb
            acct = wb.get_account_info()
            # Merge with local trade log
            state = _load_state()
            return {
                "cash":          acct["cash"],
                "total_value":   acct["total_value"],
                "total_pnl":     round(acct["total_value"] - config.PAPER_INITIAL_CAPITAL, 2),
                "total_pnl_pct": round((acct["total_value"] - config.PAPER_INITIAL_CAPITAL)
                                       / config.PAPER_INITIAL_CAPITAL * 100, 2),
                "positions":     acct["positions"],
                "trade_log":     state.get("trade_log", []),
                "mode":          acct["mode"],
            }
        except Exception as e:
            pass  # Fall through to paper

    # Paper / Robinhood fallback
    state = _load_state()
    positions_detailed = []
    for ticker, pos in state["positions"].items():
        current = prices.get(ticker, pos["entry_price"]) if prices else pos["entry_price"]
        pnl     = (current - pos["entry_price"]) * pos["shares"]
        pnl_pct = (current - pos["entry_price"]) / pos["entry_price"] * 100
        positions_detailed.append({
            "Ticker":    ticker, "Shares":    pos["shares"],
            "Entry $":   round(pos["entry_price"], 2),
            "Current $": round(current, 2),
            "P&L $":     round(pnl, 2), "P&L %": round(pnl_pct, 2),
            "Entry Date": pos["entry_date"],
        })

    total_val     = portfolio_value(prices)
    total_pnl     = total_val - config.PAPER_INITIAL_CAPITAL
    total_pnl_pct = total_pnl / config.PAPER_INITIAL_CAPITAL * 100

    broker_label = {
        "webull":    "🟡 Webull PAPER" if config.WEBULL_PAPER else "🔴 Webull LIVE",
        "robinhood": "🔴 Robinhood LIVE",
        "paper":     "🟡 PAPER TRADING",
    }.get(broker, "🟡 PAPER TRADING")

    return {
        "cash": round(state["cash"], 2), "total_value": total_val,
        "total_pnl": round(total_pnl, 2), "total_pnl_pct": round(total_pnl_pct, 2),
        "positions": positions_detailed, "trade_log": state["trade_log"],
        "mode": broker_label,
    }


def reset_paper_portfolio():
    """Reset internal paper portfolio to initial state."""
    _save_state(dict(_DEFAULT_STATE))

