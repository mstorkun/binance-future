# Candle Correlation Train-Gated Reducer - 2026-05-04

This is a backtest-only algorithm prototype. It does not change active
strategy, paper runner, testnet, or live behavior.

Source trades file: `portfolio_trades.csv`
Historical data window: `3` years

## Rule

- Never increase position size from candle or correlation features.
- Learn bad setup buckets only from the train slice.
- Reduce only buckets that were negative in train and had profit factor below `1.0`.
- Setup bucket = candle alignment + dynamic return-correlation bucket + trend-quality bucket.
- Correlation is calculated from closed-bar returns available before the trade.

## OOS Result

| segment | trades | total_pnl | win_rate_pct | profit_factor | ending_equity | max_dd | max_dd_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| oos_baseline | 104 | 6415.0900 | 81.7308 | 7.8624 | 7415.0900 | 516.2600 | 7.4038 |
| oos_train_gated_reducer | 104 | 6415.0900 | 81.7308 | 7.8624 | 7415.0900 | 516.2600 | 7.4038 |

- OOS trades: `104`
- Reduced OOS trades: `0`
- Total PnL delta: `0.0`
- Max drawdown delta: `0.0`

## Fold Summary

| fold | test_trades | reduced_test_trades | learned_rule_count |
| --- | --- | --- | --- |
| 0 | 40 | 0 | 0 |
| 1 | 40 | 0 | 0 |
| 2 | 24 | 0 | 0 |

## Reduced Bucket Contribution

_No rows._

## Decision

If OOS PnL or drawdown does not improve, this reducer stays report-only.
It should not be promoted into paper/testnet until a true entry-time
position-sizing backtest and walk-forward both show net improvement.
