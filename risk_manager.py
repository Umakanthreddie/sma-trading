"""
risk_manager.py — Trading safety guardrails.

Enforces:
  - Max position size per stock
  - Max number of open positions
  - Daily loss limit (halts trading)
  - Stop-loss per position
  - Minimum AI score to trade
"""

from datetime import date
import config


class RiskManager:
    def __init__(self, initial_capital: float = config.PAPER_INITIAL_CAPITAL):
        self.initial_capital    = initial_capital
        self.day_start_value    = initial_capital
        self.trading_halted     = False
        self.halt_reason        = ""
        self._today             = str(date.today())

    def reset_daily(self, portfolio_value: float):
        """Call at start of each trading day."""
        today = str(date.today())
        if today != self._today:
            self._today          = today
            self.day_start_value = portfolio_value
            self.trading_halted  = False
            self.halt_reason     = ""

    def check_daily_loss(self, portfolio_value: float) -> bool:
        """
        Returns True if trading should continue, False if daily loss limit hit.
        """
        if self.trading_halted:
            return False
        if self.day_start_value <= 0:
            return True
        daily_loss_pct = (portfolio_value - self.day_start_value) / self.day_start_value * 100
        if daily_loss_pct <= -config.DAILY_LOSS_LIMIT:
            self.trading_halted = True
            self.halt_reason = (
                f"Daily loss limit hit: {daily_loss_pct:.2f}% "
                f"(limit: -{config.DAILY_LOSS_LIMIT}%)"
            )
            return False
        return True

    def can_buy(self, ticker: str, ai_score: float,
                portfolio_value: float, open_positions: dict) -> tuple[bool, str]:
        """
        Check all rules before placing a buy.

        Returns:
            (allowed: bool, reason: str)
        """
        # Trading halted?
        if self.trading_halted:
            return False, f"Trading halted: {self.halt_reason}"

        # Daily loss check
        if not self.check_daily_loss(portfolio_value):
            return False, self.halt_reason

        # AI score threshold
        if ai_score < config.AI_MIN_SCORE:
            return False, f"AI score {ai_score:.0f} below minimum {config.AI_MIN_SCORE}"

        # Max open positions
        if len(open_positions) >= config.MAX_OPEN_POSITIONS:
            return False, f"Max open positions reached ({config.MAX_OPEN_POSITIONS})"

        # Already holding this stock?
        if ticker in open_positions:
            return False, f"Already holding {ticker}"

        return True, "OK"

    def position_size(self, portfolio_value: float, price: float) -> int:
        """
        Calculate safe number of shares to buy.

        Caps at MAX_POSITION_PCT% of portfolio.
        """
        max_dollars = portfolio_value * (config.MAX_POSITION_PCT / 100)
        shares      = int(max_dollars // price)
        return max(0, shares)

    def should_stop_loss(self, ticker: str, entry_price: float, current_price: float) -> bool:
        """
        Returns True if position should be sold due to stop-loss.
        """
        loss_pct = (current_price - entry_price) / entry_price * 100
        return loss_pct <= -config.STOP_LOSS_PCT

    def emergency_halt(self, reason: str = "Manual emergency stop"):
        """Immediately halt all trading."""
        self.trading_halted = True
        self.halt_reason    = reason

    def resume(self):
        """Resume trading after manual review."""
        self.trading_halted = False
        self.halt_reason    = ""

    def status(self) -> dict:
        return {
            "trading_halted":    self.trading_halted,
            "halt_reason":       self.halt_reason,
            "max_position_pct":  config.MAX_POSITION_PCT,
            "max_positions":     config.MAX_OPEN_POSITIONS,
            "daily_loss_limit":  config.DAILY_LOSS_LIMIT,
            "stop_loss_pct":     config.STOP_LOSS_PCT,
            "min_ai_score":      config.AI_MIN_SCORE,
        }
