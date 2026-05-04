# Trend/Candle Entry Walk-Forward - 2026-05-04

This is a true entry-time side-by-side research backtest. It does not
change paper, testnet, or live behavior.

Historical data window: `3` years

## Rule

- Baseline Donchian logic stays unchanged.
- Train folds learn bad setup buckets from closed-bar trend quality,
  candle-structure alignment, and dynamic symbol correlation.
- Test folds reduce only train-proven bad buckets.
- No candle/correlation feature can increase position size.

## OOS Result

| segment | trades | total_pnl | win_rate_pct | profit_factor | ending_equity | max_dd | max_dd_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_oos | 106 | 6002.3400 | 81.1321 | 5.9885 | 7002.3400 | 505.7200 | 7.3756 |
| entry_time_overlay_oos | 106 | 6002.3400 | 81.1321 | 5.9885 | 7002.3400 | 505.7200 | 7.3756 |

- OOS PnL delta: `0.0`
- OOS max DD delta: `0.0`
- Reduced overlay trades: `0`

## Fold Summary

| fold | baseline_test_trades | learned_rule_count |
| --- | --- | --- |
| 0 | 40 | 0 |
| 1 | 40 | 0 |
| 2 | 25 | 0 |

## Decision

If this report does not improve OOS PnL or drawdown, the feature remains
research-only and must not be promoted to paper/testnet.
