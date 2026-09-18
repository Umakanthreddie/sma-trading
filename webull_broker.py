"""
webull_broker.py — Webull trading integration.

Supports:
  - Webull Paper Trading (safe, uses Webull's built-in paper account)
  - Webull Live Trading  (real money — set WEBULL_PAPER = False in config)

Uses the `webull` PyPI package.
"""

import time
import config

_wb_instance  = None
_wb_logged_in = False


def _get_wb():
    """Get authenticated Webull instance (lazy singleton)."""
    global _wb_instance, _wb_logged_in
    if _wb_instance and _wb_logged_in:
        return _wb_instance

    try:
        from webull import webull, paper_webull
    except ImportError:
        raise RuntimeError(
            "webull package not installed. Run: pip install webull"
        )

    if config.WEBULL_PAPER:
        wb = paper_webull()
        wb.login(
            username=config.WEBULL_PHONE,
            password=config.WEBULL_PASSWORD,
            device_name=config.WEBULL_DEVICE_ID,
        )
    else:
        wb = webull()
        wb.login(
            username=config.WEBULL_PHONE,
            password=config.WEBULL_PASSWORD,
            device_name=config.WEBULL_DEVICE_ID,
        )

    _wb_instance  = wb
    _wb_logged_in = True
    return wb


def get_account_info() -> dict:
    """
    Fetch Webull account balance and portfolio info.

    Returns:
        {cash, total_value, positions: [...], mode}
    """
    try:
        wb        = _get_wb()
        account   = wb.get_account()
        positions = wb.get_positions() or []

        cash        = float(account.get("cashBalance", 0) or
                            account.get("usableCash", 0) or 0)
        total_value = float(account.get("netLiquidation", 0) or
                            account.get("totalMarketValue", 0) or cash)

        pos_list = []
        for p in positions:
            ticker   = p.get("ticker", {}).get("symbol", "")
            quantity = int(float(p.get("position", 0) or 0))
            cost     = float(p.get("costPrice", 0) or 0)
            mkt      = float(p.get("lastPrice", 0) or p.get("marketValue", 0) or cost)
            pnl      = (mkt - cost) * quantity
            pnl_pct  = (mkt - cost) / cost * 100 if cost else 0
            if ticker and quantity > 0:
                pos_list.append({
                    "Ticker":    ticker,
                    "Shares":    quantity,
                    "Entry $":   round(cost, 2),
                    "Current $": round(mkt, 2),
                    "P&L $":     round(pnl, 2),
                    "P&L %":     round(pnl_pct, 2),
                })

        return {
            "cash":        round(cash, 2),
            "total_value": round(total_value, 2),
            "positions":   pos_list,
            "mode":        "🟡 Webull PAPER" if config.WEBULL_PAPER else "🔴 Webull LIVE",
        }
    except Exception as e:
        return {
            "cash": 0, "total_value": 0, "positions": [],
            "mode": "❌ Webull Error", "error": str(e),
        }


def get_current_price(ticker: str) -> float:
    """Fetch real-time quote from Webull."""
    try:
        wb    = _get_wb()
        quote = wb.get_quote(ticker)
        return float(quote.get("close") or quote.get("pPrice") or 0)
    except Exception:
        return 0.0


def buy(ticker: str, shares: int, ai_score: float, reason: str) -> dict:
    """
    Place a market BUY order on Webull (paper or live).

    Returns:
        {success, ticker, shares, order_id, mode, reason}
    """
    if shares <= 0:
        return {"success": False, "ticker": ticker, "reason": "shares <= 0"}
    try:
        wb    = _get_wb()
        order = wb.place_order(
            stock=ticker,
            action="BUY",
            orderType="MKT",
            enforce="DAY",
            qty=shares,
        )
        order_id = (order or {}).get("orderId", "unknown")
        return {
            "success":  True,
            "action":   "BUY",
            "ticker":   ticker,
            "shares":   shares,
            "ai_score": ai_score,
            "reason":   reason,
            "order_id": order_id,
            "mode":     "WEBULL_PAPER" if config.WEBULL_PAPER else "WEBULL_LIVE",
        }
    except Exception as e:
        return {"success": False, "ticker": ticker, "action": "BUY", "reason": str(e)}


def sell(ticker: str, reason: str) -> dict:
    """
    Sell all shares of a position on Webull.

    Returns:
        {success, ticker, shares, order_id, mode, reason}
    """
    try:
        wb        = _get_wb()
        positions = wb.get_positions() or []
        shares    = 0
        for p in positions:
            sym = p.get("ticker", {}).get("symbol", "")
            if sym == ticker:
                shares = int(float(p.get("position", 0) or 0))
                break

        if shares <= 0:
            return {"success": False, "ticker": ticker, "reason": f"No position in {ticker}"}

        order    = wb.place_order(
            stock=ticker,
            action="SELL",
            orderType="MKT",
            enforce="DAY",
            qty=shares,
        )
        order_id = (order or {}).get("orderId", "unknown")
        return {
            "success":  True,
            "action":   "SELL",
            "ticker":   ticker,
            "shares":   shares,
            "reason":   reason,
            "order_id": order_id,
            "mode":     "WEBULL_PAPER" if config.WEBULL_PAPER else "WEBULL_LIVE",
        }
    except Exception as e:
        return {"success": False, "ticker": ticker, "action": "SELL", "reason": str(e)}


def get_order_history(count: int = 20) -> list:
    """Fetch recent order history from Webull."""
    try:
        wb     = _get_wb()
        orders = wb.get_history_orders(status="Filled", count=count) or []
        result = []
        for o in orders:
            result.append({
                "action":    o.get("action", ""),
                "ticker":    o.get("ticker", {}).get("symbol", ""),
                "shares":    o.get("totalQuantity", 0),
                "price":     o.get("avgFilledPrice", 0),
                "status":    o.get("status", ""),
                "timestamp": o.get("createTime", ""),
                "order_id":  o.get("orderId", ""),
                "mode":      "WEBULL_PAPER" if config.WEBULL_PAPER else "WEBULL_LIVE",
            })
        return result
    except Exception:
        return []
