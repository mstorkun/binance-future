# Liquidation Hunting Proxy PoC - 2026-05-04

This is a research-only high-return strategy lab report. It uses public
Binance Futures OHLCV as a liquidation proxy: large directional candle,
large volume z-score, and expanded range. It does not use private
Coinglass/Coinalyze liquidation feeds yet, does not place orders, and does
not change paper/testnet/live behavior.

## Method

Parameters are selected on the train slice and then applied to the held-out
test slice. Entries happen on the next bar open after a closed proxy event.
If TP and SL are both touched inside the same candle, the backtest assumes
the stop is hit first. A cooldown and per-day trade cap are applied so the
research does not reward high churn that only pays commission.

Target gate: net CAGR >= `80.0%` after modeled fees/slippage,
profit factor >= `1.2`, enough trades, and max drawdown within the
configured limit. Short annualized samples are blocked by a minimum OOS
sample-days gate. Capital amount is not the success metric; percentage
return after costs is.

Command: `python liquidation_hunting_report.py --symbols DOGE/USDT:USDT --timeframes 15m --days 45 --start-balance 5000 --leverage 7 --risk-grid 0.03 0.05 0.1 --min-cooldown-bars 8 --max-trades-per-day 3 --horizon-grid 12 24 36 --target-cagr-pct 80 --min-test-days 30`

## Result

- Rows: `3`
- Passing rows: `0`

| symbol | timeframe | risk_per_trade_pct | trades | total_return_pct | cagr_pct | max_dd_pct | profit_factor | sample_days | ok | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOGE/USDT:USDT | 15m | 0.1000 | 6 | 5.8561 | 105023608621.4761 | 9.9104 | 1.3109 | 17.9896 | False | insufficient_sample |
| DOGE/USDT:USDT | 15m | 0.0500 | 6 | 3.9388 | 132983932.2975 | 5.8990 | 1.3440 | 17.9896 | False | insufficient_sample |
| DOGE/USDT:USDT | 15m | 0.0300 | 6 | 2.5149 | 865360.7442 | 3.5394 | 1.3617 | 17.9896 | False | insufficient_sample |

## Decision

A pass here would only justify a stricter second pass with real liquidation
feed data and walk-forward folds. If pass count is zero, do not promote this
strategy to paper/live.
