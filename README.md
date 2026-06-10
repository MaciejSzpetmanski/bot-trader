# Paper News Trader

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)

Paper News Trader is a **paper-trading research bot** for testing whether a combination of price trends, news sentiment, and optional social/RSS feeds can produce useful trading signals in a controlled environment.

The project is designed to be conservative by default: it trades through an Alpaca paper account only, logs every decision, models slippage and fees in backtests, and includes several hard risk guards.

> **Important:** This software is for education and research only. It is not financial, investment, legal, accounting, or tax advice. Automated trading can lose money quickly. Do not connect this project to live trading without independent validation and professional review.

---

## Contents

- [Features](#features)
- [What this project does not do](#what-this-project-does-not-do)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Risk controls](#risk-controls)
- [Data sources](#data-sources)
- [Backtesting assumptions](#backtesting-assumptions)
- [Logs and outputs](#logs-and-outputs)
- [Development](#development)
- [Docker](#docker)
- [Security](#security)
- [Compliance notes](#compliance-notes)
- [License](#license)
- [Third-party licenses](#third-party-licenses)

---

## Features

- Alpaca paper-trading execution.
- Historical daily-bar market data ingestion.
- Alpaca news ingestion.
- Optional RSS ingestion for company websites, investor-relations feeds, SEC feeds, exchange feeds, and trusted news feeds.
- Optional X/Twitter recent-search adapter through Tweepy.
- Trend indicators:
  - moving averages
  - momentum
  - volatility normalization
  - simple RSI
- Sentiment scoring with VADER.
- Combined trend/news signal scoring.
- Backtester with configurable slippage and fees.
- CSV and JSONL logs.
- Unit tests.
- Dockerfile and Makefile.
- Hard risk controls and emergency stop.

---

## What this project does not do

This project does **not** guarantee profitable trades or accurate news impact predictions. Market reactions to news are noisy, fast, and often depend on context that is not visible in public headlines.

This project also does **not**:

- scrape websites that disallow scraping;
- bypass paywalls, rate limits, API restrictions, or terms of service;
- provide investment advice;
- manage real money;
- execute live trades;
- handle every regulatory, broker, market-data, or tax requirement for your jurisdiction.

The code intentionally avoids a “profit above all else” objective. A trading system should optimize within hard limits, not ignore risk.

---

## Architecture

```text
paper_news_trader/
  main.py             CLI entry point
  config.py           environment/config loader
  models.py           dataclasses and shared types
  logging_utils.py    JSONL and console logging
  indicators.py       technical indicators
  sentiment.py        sentiment scoring
  strategy.py         trend/news signal generation
  risk.py             risk guards and order-intent creation
  backtest.py         simple event-driven backtester
  data_sources.py     Alpaca, RSS, and X/Twitter adapters
  execution.py        Alpaca paper-order executor

tests/
  test_strategy.py
```

Typical flow:

```text
market/news/social data
        ↓
indicators + sentiment
        ↓
combined trading signal
        ↓
risk manager
        ↓
paper executor or backtester
        ↓
logs, trades, equity curve
```

---

## Requirements

- Python 3.11 or newer.
- Alpaca paper-trading API credentials.
- Optional: X/Twitter API access for the Tweepy adapter.
- Optional: RSS feed URLs for company/news sources.

Python dependencies are listed in [`requirements.txt`](requirements.txt).

---

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` before running paper trading.

---

## Configuration

The project reads configuration from environment variables or a `.env` file.

### Required for paper trading

```env
ALPACA_API_KEY=replace_me
ALPACA_SECRET_KEY=replace_me
ALPACA_PAPER=true
```

`ALPACA_PAPER=true` is required for execution. The executor refuses to run if paper mode is disabled.

### Strategy universe

```env
SYMBOLS=AAPL,MSFT,NVDA,TSLA,AMZN
```

### Trading cadence and safeguards

```env
LOOP_SECONDS=1800
MAX_POSITION_PCT=0.10
MAX_TOTAL_EXPOSURE_PCT=0.60
MAX_DAILY_LOSS_PCT=0.03
MAX_DRAWDOWN_PCT=0.08
STOP_LOSS_PCT=0.04
TAKE_PROFIT_PCT=0.10
MIN_SIGNAL_SCORE=0.35
MAX_TRADES_PER_DAY=8
COOLDOWN_MINUTES=60
```

### Backtest assumptions

```env
INITIAL_CASH=100000
SLIPPAGE_BPS=10
FEE_PER_TRADE=0
```

### Optional data sources

```env
RSS_FEEDS=https://example.com/investor-news/rss,https://another-source.com/feed
X_BEARER_TOKEN=replace_me
X_QUERY_TEMPLATE="{symbol} stock OR ${symbol} -is:retweet lang:en"
```

Use only data sources you are permitted to access and process.

---

## Usage

Run commands from the repository root.

### View current signals without trading

```bash
python -m paper_news_trader.main signals --symbols AAPL,MSFT,NVDA --days 180
```

### Run a historical backtest

```bash
python -m paper_news_trader.main backtest --symbols AAPL,MSFT,NVDA --days 365
```

Backtest outputs are written to `logs/`.

### Run one paper-trading cycle

```bash
python -m paper_news_trader.main paper --once
```

### Run continuously in paper mode

```bash
python -m paper_news_trader.main paper
```

The bot sleeps for `LOOP_SECONDS` between cycles.

---

## Risk controls

Risk controls are enforced before paper orders are submitted.

| Control | Purpose |
| --- | --- |
| `MAX_POSITION_PCT` | Caps the size of any single position. |
| `MAX_TOTAL_EXPOSURE_PCT` | Caps total portfolio exposure. |
| `MAX_DAILY_LOSS_PCT` | Pauses trading after a daily equity loss threshold. |
| `MAX_DRAWDOWN_PCT` | Pauses trading after a peak-to-trough drawdown threshold. |
| `STOP_LOSS_PCT` | Exits positions that fall beyond the configured loss threshold. |
| `TAKE_PROFIT_PCT` | Exits positions that reach the configured gain threshold. |
| `MAX_TRADES_PER_DAY` | Limits trade frequency. |
| `COOLDOWN_MINUTES` | Prevents repeated trading in the same symbol too quickly. |
| `PANIC_STOP` | File-based emergency stop. |

### Emergency stop

Create a file named `PANIC_STOP` in the project root:

```bash
touch PANIC_STOP
```

The risk manager treats this as a hard stop. Delete it only after you have reviewed logs, open positions, and configuration.

---

## Data sources

### Alpaca market data and news

The Alpaca adapters use the credentials in `.env` for historical bars, news, account state, positions, and paper orders.

### RSS and company websites

RSS feeds can be used for company investor-relations pages, official newsrooms, SEC feeds, exchange announcements, or trusted publishers.

Do not scrape websites unless you have permission and the site terms allow it. Prefer official APIs or RSS feeds.

### X/Twitter

The X/Twitter source is optional. It uses Tweepy only when `X_BEARER_TOKEN` is set.

API access, endpoint availability, pricing, and rate limits can change. Validate your account permissions before relying on this adapter.

---

## Backtesting assumptions

The backtester is intentionally simple. It is useful for sanity checks, not for proving that a strategy will work live.

It models:

- initial cash;
- long-only entries and exits;
- configured slippage in basis points;
- configured flat fee per trade;
- stop-loss and take-profit exits;
- equity curve and trade records.

Limitations:

- daily bars are coarse;
- intraday order timing is simplified;
- news timing may not perfectly align with market reaction windows;
- survivorship bias, market-data quality, borrow constraints, and partial fills are not fully modeled;
- paper fills can differ from live fills.

---

## Logs and outputs

The project writes logs to `logs/` by default.

| File | Description |
| --- | --- |
| `logs/bot.jsonl` | Structured event log. |
| `logs/backtest_equity.csv` | Backtest equity curve. |
| `logs/backtest_trades.csv` | Backtest trade list. |

The `logs/` directory is ignored by Git.

---

## Development

Run tests:

```bash
pytest
```

Useful Makefile targets:

```bash
make test
make backtest
make signals
```

Recommended local checks before sharing or deploying changes:

```bash
pytest
python -m compileall paper_news_trader
```

---

## Docker

Build the image:

```bash
docker build -t paper-news-trader .
```

Run a one-cycle paper bot with your `.env` file mounted:

```bash
docker run --rm --env-file .env -v "$(pwd)/logs:/app/logs" paper-news-trader \
  python -m paper_news_trader.main paper --once
```

---

## Security

- Never commit `.env`, API keys, bearer tokens, logs, or account exports.
- Use paper credentials only while developing.
- Rotate keys immediately if they are exposed.
- Keep `PANIC_STOP` available as an emergency control.
- Review dependency updates before applying them.
- Run this in an isolated environment when testing new data-source adapters.

A basic `.gitignore` is included for secrets, caches, build artifacts, and logs.

---

## Compliance notes

Before any live-trading rewrite, review:

- broker API terms and trading restrictions;
- market-data license terms;
- social-media and news-source terms;
- securities, tax, and recordkeeping rules in your jurisdiction;
- pre-trade controls, kill switches, monitoring, audit logs, and change management;
- whether the strategy creates pattern-day-trading, wash-sale, tax-lot, or reporting issues.

Consult qualified financial, legal, and tax professionals before using any derivative of this project with real money.

---

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).

SPDX identifier:

```text
MIT
```

---

## Third-party licenses

This project depends on third-party Python packages listed in [`requirements.txt`](requirements.txt). Those packages are not vendored into this repository.

A convenience summary is provided in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Regenerate and verify notices in your own environment before redistributing binaries, Docker images, or modified dependency bundles.

Recommended license-audit command:

```bash
pip install pip-licenses
pip-licenses --format=markdown --with-urls --with-license-file > THIRD_PARTY_NOTICES.generated.md
```
