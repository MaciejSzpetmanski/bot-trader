# SPDX-License-Identifier: MIT
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd

from .config import Settings
from .models import Action, NewsItem, PortfolioState, Position
from .risk import RiskManager
from .strategy import NewsTrendStrategy


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    summary: dict[str, float | int | str]


class Backtester:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.strategy = NewsTrendStrategy(settings.min_signal_score)
        self.risk = RiskManager(settings)

    def _execute_price(self, close: float, action: Action) -> float:
        slippage = self.settings.slippage_bps / 10_000
        if action == Action.BUY:
            return close * (1 + slippage)
        if action == Action.SELL:
            return close * (1 - slippage)
        return close

    def _mark_to_market(self, cash: float, positions: Dict[str, Position], price_lookup: dict[str, float]) -> float:
        equity = cash
        for symbol, pos in positions.items():
            price = price_lookup.get(symbol, pos.market_price)
            equity += pos.qty * price
        return equity

    def run(
        self,
        bars_by_symbol: dict[str, pd.DataFrame],
        news_items: Iterable[NewsItem] | None = None,
    ) -> BacktestResult:
        news_items = list(news_items or [])
        symbols = [s for s, df in bars_by_symbol.items() if df is not None and not df.empty]
        if not symbols:
            raise ValueError("No market data supplied to backtest")

        # Use common trading dates across symbols to keep accounting simple.
        common_index = None
        for df in bars_by_symbol.values():
            idx = pd.DatetimeIndex(df.index).normalize()
            common_index = idx if common_index is None else common_index.intersection(idx)
        dates = sorted(common_index.unique()) if common_index is not None else []
        if len(dates) < 80:
            raise ValueError("Need at least 80 common trading days for this backtest")

        cash = float(self.settings.initial_cash)
        positions: dict[str, Position] = {}
        start_equity = cash
        peak_equity = cash
        trades_today = 0
        equity_rows: list[dict] = []
        trade_rows: list[dict] = []

        prepared = {s: df.copy() for s, df in bars_by_symbol.items()}
        for s, df in prepared.items():
            df.index = pd.DatetimeIndex(df.index).normalize()
            prepared[s] = df[~df.index.duplicated(keep="last")]

        for i, date in enumerate(dates):
            price_lookup = {s: float(prepared[s].loc[date, "close"]) for s in symbols if date in prepared[s].index}
            for symbol, pos in list(positions.items()):
                if symbol in price_lookup:
                    positions[symbol] = Position(symbol, pos.qty, pos.avg_entry_price, price_lookup[symbol])

            equity = self._mark_to_market(cash, positions, price_lookup)
            peak_equity = max(peak_equity, equity)
            portfolio = PortfolioState(
                cash=cash,
                equity=equity,
                positions=positions,
                start_of_day_equity=start_equity,
                peak_equity=peak_equity,
                trades_today=trades_today,
            )

            # First enforce stop-loss / take-profit exits.
            for symbol in list(positions.keys()):
                intent = self.risk.should_exit_position(symbol, portfolio)
                if intent and symbol in price_lookup:
                    px = self._execute_price(price_lookup[symbol], Action.SELL)
                    qty = min(intent.qty, positions[symbol].qty)
                    cash += qty * px - self.settings.fee_per_trade
                    trade_rows.append({"date": date, "symbol": symbol, "action": "SELL", "qty": qty, "price": px, "reason": intent.reason})
                    del positions[symbol]
                    trades_today += 1

            if i >= 65:
                historical = {s: prepared[s].loc[:date].tail(120) for s in symbols}
                todays_news = [
                    n for n in news_items
                    if n.timestamp.date() <= pd.Timestamp(date).date()
                ]
                signals = self.strategy.generate_signals(symbols, historical, todays_news)
                for symbol, signal in signals.items():
                    if symbol not in price_lookup:
                        continue
                    equity = self._mark_to_market(cash, positions, price_lookup)
                    portfolio = PortfolioState(cash, equity, positions, start_equity, peak_equity, trades_today)
                    intent = self.risk.order_from_signal(signal, portfolio, price_lookup[symbol])
                    if not intent:
                        continue
                    px = self._execute_price(price_lookup[symbol], intent.action)
                    if intent.action == Action.BUY:
                        cost = intent.qty * px + self.settings.fee_per_trade
                        if cost <= cash:
                            cash -= cost
                            positions[symbol] = Position(symbol, intent.qty, px, price_lookup[symbol])
                            trade_rows.append({"date": date, "symbol": symbol, "action": "BUY", "qty": intent.qty, "price": px, "reason": intent.reason})
                            trades_today += 1
                    elif intent.action == Action.SELL and symbol in positions:
                        qty = min(intent.qty, positions[symbol].qty)
                        cash += qty * px - self.settings.fee_per_trade
                        trade_rows.append({"date": date, "symbol": symbol, "action": "SELL", "qty": qty, "price": px, "reason": intent.reason})
                        del positions[symbol]
                        trades_today += 1

            equity = self._mark_to_market(cash, positions, price_lookup)
            equity_rows.append({"date": date, "cash": cash, "equity": equity, "positions": len(positions)})

        equity_curve = pd.DataFrame(equity_rows)
        trades = pd.DataFrame(trade_rows)
        final_equity = float(equity_curve["equity"].iloc[-1])
        total_return = final_equity / self.settings.initial_cash - 1
        returns = equity_curve["equity"].pct_change().dropna()
        sharpe = float((returns.mean() / returns.std()) * (252 ** 0.5)) if returns.std() and len(returns) > 2 else 0.0
        max_drawdown = float((equity_curve["equity"] / equity_curve["equity"].cummax() - 1).min())

        summary = {
            "symbols": ",".join(symbols),
            "start_equity": self.settings.initial_cash,
            "final_equity": final_equity,
            "total_return_pct": total_return * 100,
            "max_drawdown_pct": max_drawdown * 100,
            "sharpe_estimate": sharpe,
            "trades": int(len(trades)),
        }
        return BacktestResult(equity_curve, trades, summary)

    @staticmethod
    def save(result: BacktestResult, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        result.equity_curve.to_csv(out_dir / "backtest_equity.csv", index=False)
        result.trades.to_csv(out_dir / "backtest_trades.csv", index=False)
        pd.DataFrame([result.summary]).to_csv(out_dir / "backtest_summary.csv", index=False)
