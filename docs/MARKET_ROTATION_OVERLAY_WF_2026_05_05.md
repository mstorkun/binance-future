# Market Rotation Overlay Walk-Forward - 2026-05-05

Status: diagnostic-only. This does not change paper, testnet, or live behavior.

Method: train on earlier trades, learn rotation buckets with weak/negative
train behavior, then reduce those buckets only in the next chronological
test slice. This is trade-level research, not a live execution permission.

## Summary

| segment | trades | active_trades | win_rate_pct | pnl | mean_return_pct | profit_factor |
| --- | --- | --- | --- | --- | --- | --- |
| baseline_test | 120 | 120 | 85.8333 | 6886.98 | 0.9541 | 31.1677 |
| rotation_overlay_test | 120 | 120 | 85.8333 | 6886.98 | 0.9541 | 31.1677 |

Delta PnL: `0.0`
Reduced trades: `0`

## Folds

| fold | test_start | test_end | bad_bucket_count | reduced_trades | baseline_pnl | overlay_pnl | delta_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2024-11-03 20:00:00+00:00 | 2025-04-03 20:00:00+00:00 | 0 | 0 | 1464.5 | 1464.5 | 0.0 |
| 2 | 2025-04-03 20:00:00+00:00 | 2025-08-17 20:00:00+00:00 | 0 | 0 | 1285.07 | 1285.07 | 0.0 |
| 3 | 2025-08-23 00:00:00+00:00 | 2026-01-29 20:00:00+00:00 | 0 | 0 | 4137.41 | 4137.41 | 0.0 |

## Learned Buckets

- Fold 1: (none)
- Fold 2: (none)
- Fold 3: (none)

## Decision

This remains `benchmark_only`. A production gate would need a real
entry-time portfolio backtest, severe cost stress, enough folds, and no
regression in crisis/tail behavior before any activation.
