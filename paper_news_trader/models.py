# SPDX-License-Identifier: MIT
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class NewsItem:
    symbol: str
    timestamp: datetime
    headline: str
    summary: str = ""
    source: str = ""
    url: str = ""

    @property
    def text(self) -> str:
        return f"{self.headline}. {self.summary}".strip()


@dataclass
class Signal:
    symbol: str
    timestamp: datetime
    action: Action
    score: float
    trend_score: float
    sentiment_score: float
    confidence: float
    reasons: List[str] = field(default_factory=list)


@dataclass
class Position:
    symbol: str
    qty: int
    avg_entry_price: float
    market_price: float

    @property
    def market_value(self) -> float:
        return self.qty * self.market_price

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.avg_entry_price <= 0:
            return 0.0
        return self.market_price / self.avg_entry_price - 1.0


@dataclass
class PortfolioState:
    cash: float
    equity: float
    positions: Dict[str, Position]
    start_of_day_equity: float
    peak_equity: float
    trades_today: int = 0


@dataclass
class OrderIntent:
    symbol: str
    action: Action
    qty: int
    reason: str
    limit_price: Optional[float] = None
