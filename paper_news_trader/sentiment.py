# SPDX-License-Identifier: MIT
from __future__ import annotations

import re
from typing import Iterable, Tuple

from .models import NewsItem

_CLEAN_RE = re.compile(r"https?://\S+|www\.\S+|\s+")

_POSITIVE = {
    "beat", "beats", "growth", "strong", "excellent", "profit", "profits", "record", "upgrade",
    "bullish", "outperform", "surge", "surges", "gain", "gains", "demand", "positive", "raises",
    "raised", "expands", "approval", "approved", "partnership", "buyback", "dividend",
}
_NEGATIVE = {
    "miss", "misses", "weak", "loss", "losses", "downgrade", "bearish", "underperform", "fall",
    "falls", "drop", "drops", "lawsuit", "probe", "investigation", "recall", "negative", "cuts",
    "cut", "layoff", "layoffs", "bankruptcy", "fraud", "warning", "warns",
}


class _LexiconFallback:
    def polarity_scores(self, text: str) -> dict[str, float]:
        words = re.findall(r"[a-zA-Z]+", text.lower())
        if not words:
            return {"compound": 0.0}
        score = 0
        for word in words:
            if word in _POSITIVE:
                score += 1
            elif word in _NEGATIVE:
                score -= 1
        # Roughly emulate VADER's compound range.
        compound = max(-1.0, min(1.0, score / 5))
        return {"compound": compound}


class SentimentEngine:
    def __init__(self) -> None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

            self.analyzer = SentimentIntensityAnalyzer()
        except Exception:
            self.analyzer = _LexiconFallback()

    @staticmethod
    def clean_text(text: str) -> str:
        text = text.replace("$", " ")
        text = _CLEAN_RE.sub(" ", text)
        return text.strip()

    def score_text(self, text: str) -> float:
        clean = self.clean_text(text)
        if not clean:
            return 0.0
        return float(self.analyzer.polarity_scores(clean)["compound"])

    def score_items(self, items: Iterable[NewsItem]) -> Tuple[float, list[str]]:
        scores: list[float] = []
        headlines: list[str] = []
        for item in items:
            score = self.score_text(item.text)
            scores.append(score)
            if item.headline:
                headlines.append(item.headline[:160])
        if not scores:
            return 0.0, ["no recent news/social items"]
        avg = sum(scores) / len(scores)
        return float(avg), [f"sentiment from {len(scores)} recent items"] + headlines[:3]
