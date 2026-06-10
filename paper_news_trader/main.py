# SPDX-License-Identifier: MIT
from __future__ import annotations

import argparse
import logging
import time
from collections import defaultdict
from pathlib import Path

from .backtest import Backtester
from .config import Settings
from .data_sources import AlpacaMarketData, AlpacaNewsSource, CompositeNewsSource, RSSNewsSource, XRecentSearchSource
from .execution import AlpacaPaperExecutor
from .logging_utils import JsonlLogger, setup_console_logging
from .risk import RiskManager
from .strategy import NewsTrendStrategy

LOGGER = logging.getLogger(__name__)


def parse_symbols(cli_value: str | None, settings: Settings) -> list[str]:
    if cli_value:
        return [s.strip().upper() for s in cli_value.split(",") if s.strip()]
    return [s.upper() for s in settings.symbols]


def build_news_source(settings: Settings) -> CompositeNewsSource:
    sources = []
    if settings.alpaca_api_key and settings.alpaca_secret_key:
        sources.append(AlpacaNewsSource(settings))
    if settings.rss_feeds:
        sources.append(RSSNewsSource(settings.rss_feeds))
    if settings.x_bearer_token:
        sources.append(XRecentSearchSource(settings.x_bearer_token, settings.x_query_template))
    return CompositeNewsSource(sources)


def command_backtest(args) -> None:
    settings = Settings.load(args.env)
    symbols = parse_symbols(args.symbols, settings)
    log = JsonlLogger(settings.log_dir / "bot.jsonl")
    market = AlpacaMarketData(settings)
    news = build_news_source(settings)

    bars_by_symbol = {}
    for symbol in symbols:
        LOGGER.info("Downloading %s bars", symbol)
        bars_by_symbol[symbol] = market.get_bars(symbol, days=args.days)

    LOGGER.info("Fetching news/social items")
    news_items = news.fetch(symbols, lookback_hours=min(args.days * 24, 168))

    backtester = Backtester(settings)
    result = backtester.run(bars_by_symbol, news_items)
    Backtester.save(result, settings.log_dir)
    log.write("backtest_summary", result.summary)

    print("Backtest summary")
    for key, value in result.summary.items():
        print(f"{key}: {value}")
    print(f"Wrote CSV logs to {settings.log_dir.resolve()}")


def command_paper(args) -> None:
    settings = Settings.load(args.env)
    settings.validate_for_paper()
    symbols = parse_symbols(args.symbols, settings)
    log = JsonlLogger(settings.log_dir / "bot.jsonl")

    market = AlpacaMarketData(settings)
    news = build_news_source(settings)
    strategy = NewsTrendStrategy(settings.min_signal_score)
    risk = RiskManager(settings)
    executor = AlpacaPaperExecutor(settings)

    while True:
        try:
            bars_by_symbol = {symbol: market.get_bars(symbol, days=180) for symbol in symbols}
            latest_prices = {
                symbol: float(df["close"].iloc[-1])
                for symbol, df in bars_by_symbol.items()
                if df is not None and not df.empty
            }
            items = news.fetch(symbols, lookback_hours=72)
            signals = strategy.generate_signals(symbols, bars_by_symbol, items)
            portfolio = executor.portfolio_state(latest_prices)

            guard = risk.guardrail_reason(portfolio)
            if guard:
                LOGGER.warning("Trading paused: %s", guard)
                log.write("guardrail", {"reason": guard, "equity": portfolio.equity})
            else:
                for symbol in symbols:
                    exit_intent = risk.should_exit_position(symbol, portfolio)
                    if exit_intent:
                        result = executor.submit(exit_intent)
                        risk.mark_trade(symbol)
                        log.write("order_submitted", {"intent": exit_intent, "broker_result": str(result)})
                        portfolio = executor.portfolio_state(latest_prices)

                for symbol, signal in signals.items():
                    log.write("signal", {"signal": signal})
                    intent = risk.order_from_signal(signal, portfolio, latest_prices.get(symbol))
                    if intent:
                        result = executor.submit(intent)
                        risk.mark_trade(symbol)
                        log.write("order_submitted", {"intent": intent, "broker_result": str(result)})
                        portfolio = executor.portfolio_state(latest_prices)

        except KeyboardInterrupt:
            print("Stopping paper bot.")
            return
        except Exception as exc:
            LOGGER.exception("Bot loop error: %s", exc)
            log.write("error", {"error": str(exc)})

        if args.once:
            return
        time.sleep(settings.loop_seconds)


def command_signals(args) -> None:
    settings = Settings.load(args.env)
    symbols = parse_symbols(args.symbols, settings)
    market = AlpacaMarketData(settings)
    news = build_news_source(settings)
    strategy = NewsTrendStrategy(settings.min_signal_score)

    bars_by_symbol = {symbol: market.get_bars(symbol, days=args.days) for symbol in symbols}
    items = news.fetch(symbols, lookback_hours=72)
    signals = strategy.generate_signals(symbols, bars_by_symbol, items)
    by_symbol = defaultdict(list)
    for item in items:
        by_symbol[item.symbol].append(item)

    for symbol, signal in signals.items():
        print(f"{symbol}: {signal.action.value} score={signal.score:.3f} trend={signal.trend_score:.3f} sentiment={signal.sentiment_score:.3f}")
        for reason in signal.reasons[:5]:
            print(f"  - {reason}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Paper News Trader")
    parser.add_argument("--env", default=None, help="Path to .env file")
    sub = parser.add_subparsers(required=True)

    b = sub.add_parser("backtest", help="Run historical backtest")
    b.add_argument("--symbols", default=None, help="Comma-separated symbols")
    b.add_argument("--days", type=int, default=365)
    b.set_defaults(func=command_backtest)

    p = sub.add_parser("paper", help="Run Alpaca paper bot")
    p.add_argument("--symbols", default=None, help="Comma-separated symbols")
    p.add_argument("--once", action="store_true", help="Run one loop and exit")
    p.set_defaults(func=command_paper)

    s = sub.add_parser("signals", help="Print current signals without trading")
    s.add_argument("--symbols", default=None, help="Comma-separated symbols")
    s.add_argument("--days", type=int, default=180)
    s.set_defaults(func=command_signals)
    return parser


def main() -> None:
    setup_console_logging()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
