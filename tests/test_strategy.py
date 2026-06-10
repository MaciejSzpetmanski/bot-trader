# SPDX-License-Identifier: MIT
from datetime import datetime, timezone

import pandas as pd

from paper_news_trader.models import Action, NewsItem, PortfolioState
from paper_news_trader.strategy import NewsTrendStrategy
from paper_news_trader.config import Settings
from paper_news_trader.risk import RiskManager


def make_bars(n=90, start=100, step=1):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = [start + i * step for i in range(n)]
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": 1000}, index=idx)


def test_strategy_buys_positive_trend_and_sentiment():
    strategy = NewsTrendStrategy(min_signal_score=0.25)
    news = [NewsItem("AAPL", datetime.now(timezone.utc), "Apple reports excellent growth and strong demand")]
    signal = strategy.generate_signal("AAPL", make_bars(), news)
    assert signal.action == Action.BUY
    assert signal.score > 0


def test_risk_blocks_on_daily_loss():
    settings = Settings(max_daily_loss_pct=0.03)
    risk = RiskManager(settings)
    portfolio = PortfolioState(cash=97000, equity=97000, positions={}, start_of_day_equity=100000, peak_equity=100000)
    assert risk.guardrail_reason(portfolio) is not None
