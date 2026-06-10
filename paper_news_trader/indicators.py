# SPDX-License-Identifier: MIT
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def momentum(series: pd.Series, periods: int) -> pd.Series:
    return series.pct_change(periods)


def volatility(series: pd.Series, window: int = 20) -> pd.Series:
    return series.pct_change().rolling(window).std()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def normalized_trend_score(bars: pd.DataFrame) -> tuple[float, list[str]]:
    """Return a score in roughly [-1, 1] plus human-readable reasons."""
    if bars is None or len(bars) < 65:
        return 0.0, ["not enough market history"]

    close = bars["close"].astype(float)
    s10 = sma(close, 10).iloc[-1]
    s30 = sma(close, 30).iloc[-1]
    s60 = sma(close, 60).iloc[-1]
    mom5 = momentum(close, 5).iloc[-1]
    mom20 = momentum(close, 20).iloc[-1]
    vol20 = volatility(close, 20).iloc[-1]
    rsi14 = rsi(close, 14).iloc[-1]

    reasons: list[str] = []
    score = 0.0

    if s10 > s30:
        score += 0.25
        reasons.append("10-day SMA above 30-day SMA")
    else:
        score -= 0.25
        reasons.append("10-day SMA below 30-day SMA")

    if s30 > s60:
        score += 0.25
        reasons.append("30-day SMA above 60-day SMA")
    else:
        score -= 0.25
        reasons.append("30-day SMA below 60-day SMA")

    # Volatility normalization keeps momentum from dominating high-volatility names.
    vol_denom = max(float(vol20), 0.005)
    score += float(np.clip(mom5 / vol_denom * 0.05, -0.25, 0.25))
    score += float(np.clip(mom20 / vol_denom * 0.03, -0.25, 0.25))

    if rsi14 > 75:
        score -= 0.10
        reasons.append("RSI is overbought")
    elif rsi14 < 30:
        score += 0.10
        reasons.append("RSI is oversold")
    else:
        reasons.append("RSI is neutral")

    return float(np.clip(score, -1.0, 1.0)), reasons
