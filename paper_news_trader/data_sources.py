# SPDX-License-Identifier: MIT
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Protocol

import pandas as pd
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import Settings
from .models import NewsItem

LOGGER = logging.getLogger(__name__)


class MarketDataSource(Protocol):
    def get_bars(self, symbol: str, days: int = 365) -> pd.DataFrame: ...
    def latest_price(self, symbol: str) -> float | None: ...


class NewsSource(Protocol):
    def fetch(self, symbols: Iterable[str], lookback_hours: int = 72) -> List[NewsItem]: ...


class AlpacaMarketData:
    def __init__(self, settings: Settings):
        self.settings = settings
        from alpaca.data.historical import StockHistoricalDataClient

        self.client = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def get_bars(self, symbol: str, days: int = 365) -> pd.DataFrame:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        df = self.client.get_stock_bars(req).df
        if df is None or df.empty:
            return pd.DataFrame()
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol)
        df = df.sort_index()
        return df[["open", "high", "low", "close", "volume"]].copy()

    def latest_price(self, symbol: str) -> float | None:
        bars = self.get_bars(symbol, days=10)
        if bars.empty:
            return None
        return float(bars["close"].iloc[-1])


class AlpacaNewsSource:
    def __init__(self, settings: Settings):
        self.settings = settings
        try:
            from alpaca.data.historical.news import NewsClient
        except Exception:
            from alpaca.data.historical import NewsClient

        self.client = NewsClient(settings.alpaca_api_key, settings.alpaca_secret_key)

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def fetch(self, symbols: Iterable[str], lookback_hours: int = 72) -> List[NewsItem]:
        from alpaca.data.requests import NewsRequest

        items: list[NewsItem] = []
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=lookback_hours)

        for symbol in symbols:
            req = NewsRequest(symbols=symbol, start=start, end=end, limit=50)
            try:
                articles = self.client.get_news(req)
            except Exception as exc:
                LOGGER.warning("Alpaca news failed for %s: %s", symbol, exc)
                continue
            for article in articles or []:
                timestamp = getattr(article, "created_at", None) or datetime.now(timezone.utc)
                items.append(
                    NewsItem(
                        symbol=symbol,
                        timestamp=timestamp,
                        headline=getattr(article, "headline", "") or "",
                        summary=getattr(article, "summary", "") or "",
                        source=getattr(article, "source", "alpaca") or "alpaca",
                        url=getattr(article, "url", "") or "",
                    )
                )
        return items


class RSSNewsSource:
    def __init__(self, feeds: list[str]):
        self.feeds = feeds

    @staticmethod
    def _entry_time(entry) -> datetime:
        if getattr(entry, "published_parsed", None):
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if getattr(entry, "updated_parsed", None):
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        return datetime.now(timezone.utc)

    def fetch(self, symbols: Iterable[str], lookback_hours: int = 72) -> List[NewsItem]:
        if not self.feeds:
            return []

        import feedparser

        symbols_list = list(symbols)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        out: list[NewsItem] = []

        for feed_url in self.feeds:
            parsed = feedparser.parse(feed_url)
            feed_name = getattr(parsed.feed, "title", feed_url)
            for entry in parsed.entries:
                title = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                text = f"{title} {summary}".upper()
                ts = self._entry_time(entry)
                if ts < cutoff:
                    continue
                matched = [s for s in symbols_list if s.upper() in text]
                for symbol in matched:
                    out.append(
                        NewsItem(
                            symbol=symbol,
                            timestamp=ts,
                            headline=title,
                            summary=summary,
                            source=feed_name,
                            url=getattr(entry, "link", ""),
                        )
                    )
        return out


class XRecentSearchSource:
    """Optional X/Twitter source. Requires X API access and a bearer token."""

    def __init__(self, bearer_token: str, query_template: str):
        self.bearer_token = bearer_token
        self.query_template = query_template
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import tweepy

            self._client = tweepy.Client(self.bearer_token, wait_on_rate_limit=True)
        return self._client

    def fetch(self, symbols: Iterable[str], lookback_hours: int = 72) -> List[NewsItem]:
        if not self.bearer_token:
            return []
        out: list[NewsItem] = []
        start_time = datetime.now(timezone.utc) - timedelta(hours=min(lookback_hours, 168))
        for symbol in symbols:
            query = self.query_template.format(symbol=symbol)
            try:
                response = self.client.search_recent_tweets(
                    query=query,
                    max_results=25,
                    start_time=start_time,
                    tweet_fields=["created_at", "lang"],
                )
            except Exception as exc:
                LOGGER.warning("X recent search failed for %s: %s", symbol, exc)
                continue
            for tweet in response.data or []:
                out.append(
                    NewsItem(
                        symbol=symbol,
                        timestamp=getattr(tweet, "created_at", datetime.now(timezone.utc)),
                        headline=getattr(tweet, "text", "")[:240],
                        summary="",
                        source="x_recent_search",
                        url=f"https://x.com/i/web/status/{tweet.id}",
                    )
                )
        return out


class CompositeNewsSource:
    def __init__(self, sources: list[NewsSource]):
        self.sources = sources

    def fetch(self, symbols: Iterable[str], lookback_hours: int = 72) -> List[NewsItem]:
        out: list[NewsItem] = []
        for source in self.sources:
            try:
                out.extend(source.fetch(symbols, lookback_hours=lookback_hours))
            except Exception as exc:
                LOGGER.warning("News source failed: %s", exc)
        return out
