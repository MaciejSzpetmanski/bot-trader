# SPDX-License-Identifier: MIT
from __future__ import annotations

import logging
from datetime import datetime, timezone

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import Settings
from .models import Action, OrderIntent, PortfolioState, Position

LOGGER = logging.getLogger(__name__)


class AlpacaPaperExecutor:
    def __init__(self, settings: Settings):
        settings.validate_for_paper()
        self.settings = settings
        from alpaca.trading.client import TradingClient

        self.client = TradingClient(settings.alpaca_api_key, settings.alpaca_secret_key, paper=True)
        self._start_equity = self._account_equity()
        self._peak_equity = self._start_equity
        self._day = datetime.now(timezone.utc).date()
        self._trades_today = 0

    def _account_equity(self) -> float:
        account = self.client.get_account()
        return float(account.equity)

    def _account_cash(self) -> float:
        account = self.client.get_account()
        return float(account.cash)

    def portfolio_state(self, market_prices: dict[str, float]) -> PortfolioState:
        today = datetime.now(timezone.utc).date()
        equity = self._account_equity()
        if today != self._day:
            self._day = today
            self._start_equity = equity
            self._trades_today = 0
        self._peak_equity = max(self._peak_equity, equity)

        positions: dict[str, Position] = {}
        try:
            raw_positions = self.client.get_all_positions()
        except Exception as exc:
            LOGGER.warning("Could not fetch positions: %s", exc)
            raw_positions = []

        for p in raw_positions:
            symbol = p.symbol
            market_price = float(getattr(p, "current_price", 0) or market_prices.get(symbol, 0) or 0)
            positions[symbol] = Position(
                symbol=symbol,
                qty=int(float(p.qty)),
                avg_entry_price=float(p.avg_entry_price),
                market_price=market_price,
            )

        return PortfolioState(
            cash=self._account_cash(),
            equity=equity,
            positions=positions,
            start_of_day_equity=self._start_equity,
            peak_equity=self._peak_equity,
            trades_today=self._trades_today,
        )

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def submit(self, intent: OrderIntent):
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        side = OrderSide.BUY if intent.action == Action.BUY else OrderSide.SELL
        order = MarketOrderRequest(
            symbol=intent.symbol,
            qty=intent.qty,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        result = self.client.submit_order(order)
        self._trades_today += 1
        LOGGER.info("Submitted %s %s qty=%s reason=%s", intent.action, intent.symbol, intent.qty, intent.reason)
        return result
