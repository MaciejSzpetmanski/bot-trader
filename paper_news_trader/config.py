# SPDX-License-Identifier: MIT
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return float(value)


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return int(value)


def _csv(name: str, default: str = "") -> List[str]:
    value = os.getenv(name, default)
    return [x.strip() for x in value.split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True
    symbols: List[str] = field(default_factory=lambda: ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"])

    loop_seconds: int = 1800

    max_position_pct: float = 0.10
    max_total_exposure_pct: float = 0.60
    max_daily_loss_pct: float = 0.03
    max_drawdown_pct: float = 0.08
    stop_loss_pct: float = 0.04
    take_profit_pct: float = 0.10
    min_signal_score: float = 0.35
    max_trades_per_day: int = 8
    cooldown_minutes: int = 60

    initial_cash: float = 100_000.0
    slippage_bps: float = 10.0
    fee_per_trade: float = 0.0

    rss_feeds: List[str] = field(default_factory=list)
    x_bearer_token: str = ""
    x_query_template: str = "{symbol} stock OR ${symbol} -is:retweet lang:en"

    log_dir: Path = Path("logs")
    panic_file: Path = Path("PANIC_STOP")

    @staticmethod
    def load(env_file: str | None = None) -> "Settings":
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        return Settings(
            alpaca_api_key=os.getenv("ALPACA_API_KEY", ""),
            alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            alpaca_paper=_bool("ALPACA_PAPER", True),
            symbols=_csv("SYMBOLS", "AAPL,MSFT,NVDA,TSLA,AMZN"),
            loop_seconds=_int("LOOP_SECONDS", 1800),
            max_position_pct=_float("MAX_POSITION_PCT", 0.10),
            max_total_exposure_pct=_float("MAX_TOTAL_EXPOSURE_PCT", 0.60),
            max_daily_loss_pct=_float("MAX_DAILY_LOSS_PCT", 0.03),
            max_drawdown_pct=_float("MAX_DRAWDOWN_PCT", 0.08),
            stop_loss_pct=_float("STOP_LOSS_PCT", 0.04),
            take_profit_pct=_float("TAKE_PROFIT_PCT", 0.10),
            min_signal_score=_float("MIN_SIGNAL_SCORE", 0.35),
            max_trades_per_day=_int("MAX_TRADES_PER_DAY", 8),
            cooldown_minutes=_int("COOLDOWN_MINUTES", 60),
            initial_cash=_float("INITIAL_CASH", 100_000.0),
            slippage_bps=_float("SLIPPAGE_BPS", 10.0),
            fee_per_trade=_float("FEE_PER_TRADE", 0.0),
            rss_feeds=_csv("RSS_FEEDS", ""),
            x_bearer_token=os.getenv("X_BEARER_TOKEN", ""),
            x_query_template=os.getenv("X_QUERY_TEMPLATE", "{symbol} stock OR ${symbol} -is:retweet lang:en"),
            log_dir=Path(os.getenv("LOG_DIR", "logs")),
            panic_file=Path(os.getenv("PANIC_FILE", "PANIC_STOP")),
        )

    def validate_for_paper(self) -> None:
        if not self.alpaca_api_key or not self.alpaca_secret_key:
            raise ValueError("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in .env")
        if not self.alpaca_paper:
            raise ValueError("This project refuses to run execution unless ALPACA_PAPER=true")
        if not self.symbols:
            raise ValueError("SYMBOLS cannot be empty")
