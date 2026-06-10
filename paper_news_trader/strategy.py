# SPDX-License-Identifier: MIT
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .indicators import normalized_trend_score
from .models import Action, NewsItem, Signal
from .sentiment import SentimentEngine


class NewsTrendStrategy:
    def __init__(self, min_signal_score: float = 0.35):
        self.min_signal_score = min_signal_score
        self.sentiment = SentimentEngine()

    @staticmethod
    def _clip(score: float) -> float:
        return float(np.clip(score, -1.0, 1.0))

    def generate_signal(self, symbol: str, bars: pd.DataFrame, news_items: list[NewsItem]) -> Signal:
        trend, trend_reasons = normalized_trend_score(bars)
        sent, sent_reasons = self.sentiment.score_items(news_items)

        # Trend gets more weight than text because sentiment models are fragile and noisy.
        score = self._clip(0.65 * trend + 0.35 * sent)
        confidence = min(1.0, abs(score) + min(len(news_items), 20) / 100)

        if score >= self.min_signal_score:
            action = Action.BUY
        elif score <= -self.min_signal_score:
            action = Action.SELL
        else:
            action = Action.HOLD

        return Signal(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            action=action,
            score=score,
            trend_score=trend,
            sentiment_score=sent,
            confidence=float(confidence),
            reasons=trend_reasons + sent_reasons,
        )

    def generate_signals(
        self,
        symbols: list[str],
        bars_by_symbol: dict[str, pd.DataFrame],
        news_items: list[NewsItem],
    ) -> dict[str, Signal]:
        grouped: dict[str, list[NewsItem]] = defaultdict(list)
        for item in news_items:
            grouped[item.symbol].append(item)

        return {
            symbol: self.generate_signal(symbol, bars_by_symbol.get(symbol, pd.DataFrame()), grouped[symbol])
            for symbol in symbols
        }
