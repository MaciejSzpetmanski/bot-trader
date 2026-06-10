.PHONY: test backtest signals

test:
	pytest -q

signals:
	python -m paper_news_trader.main signals --symbols AAPL,MSFT,NVDA

backtest:
	python -m paper_news_trader.main backtest --symbols AAPL,MSFT,NVDA --days 365
