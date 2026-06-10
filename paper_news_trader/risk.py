# SPDX-License-Identifier: MIT
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

from .config import Settings
from .models import Action, OrderIntent, PortfolioState, Signal


class RiskManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.last_trade_at: Dict[str, datetime] = {}

    def panic_stop(self) -> tuple[bool, str | None]:
        if Path(self.settings.panic_file).exists():
            return True, f"panic file exists: {self.settings.panic_file}"
        return False, None

    def guardrail_reason(self, portfolio: PortfolioState) -> str | None:
        panic, panic_reason = self.panic_stop()
        if panic:
            return panic_reason

        if portfolio.start_of_day_equity > 0:
            daily_loss = (portfolio.start_of_day_equity - portfolio.equity) / portfolio.start_of_day_equity
            if daily_loss >= self.settings.max_daily_loss_pct:
                return f"daily loss kill switch: {daily_loss:.2%}"

        if portfolio.peak_equity > 0:
            drawdown = (portfolio.peak_equity - portfolio.equity) / portfolio.peak_equity
            if drawdown >= self.settings.max_drawdown_pct:
                return f"max drawdown kill switch: {drawdown:.2%}"

        if portfolio.trades_today >= self.settings.max_trades_per_day:
            return "max trades per day reached"

        return None

    def total_exposure(self, portfolio: PortfolioState) -> float:
        return sum(abs(p.market_value) for p in portfolio.positions.values())

    def should_exit_position(self, symbol: str, portfolio: PortfolioState) -> OrderIntent | None:
        position = portfolio.positions.get(symbol)
        if position is None or position.qty <= 0:
            return None

        if position.unrealized_pnl_pct >= self.settings.take_profit_pct:
            return OrderIntent(symbol=symbol, action=Action.SELL, qty=position.qty, reason="take profit")

        if position.unrealized_pnl_pct <= -self.settings.stop_loss_pct:
            return OrderIntent(symbol=symbol, action=Action.SELL, qty=position.qty, reason="stop loss")

        return None

    def order_from_signal(
        self,
        signal: Signal,
        portfolio: PortfolioState,
        latest_price: float | None,
    ) -> OrderIntent | None:
        guard = self.guardrail_reason(portfolio)
        if guard:
            return None
        if latest_price is None or latest_price <= 0:
            return None

        now = datetime.now(timezone.utc)
        last = self.last_trade_at.get(signal.symbol)
        if last and now - last < timedelta(minutes=self.settings.cooldown_minutes):
            return None

        current = portfolio.positions.get(signal.symbol)
        current_qty = current.qty if current else 0

        if signal.action == Action.SELL and current_qty > 0:
            return OrderIntent(signal.symbol, Action.SELL, current_qty, f"strategy sell score={signal.score:.3f}")

        if signal.action != Action.BUY or current_qty > 0:
            return None

        max_position_value = portfolio.equity * self.settings.max_position_pct
        available_exposure = portfolio.equity * self.settings.max_total_exposure_pct - self.total_exposure(portfolio)
        budget = min(max_position_value, available_exposure, portfolio.cash)
        qty = int(budget // latest_price)
        if qty <= 0:
            return None

        return OrderIntent(signal.symbol, Action.BUY, qty, f"strategy buy score={signal.score:.3f}")

    def mark_trade(self, symbol: str) -> None:
        self.last_trade_at[symbol] = datetime.now(timezone.utc)
