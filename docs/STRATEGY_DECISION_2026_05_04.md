# Strategy Decision - 2026-05-04

This is a research decision note, not investment advice and not live
approval.

## Decision

- Verdict: `benchmark_only`
- Keep live trading blocked.
- Keep Donchian as a benchmark/research line only.
- Do not activate trend/candle/correlation reducers in paper/testnet.
- If research continues, use a small predictive-funding PoC next; no executor.

## Evidence

| metric | value |
| --- | --- |
| final_equity | 11271.7591 |
| total_return_pct | 1027.1759 |
| sharpe | 3.6935 |
| deflated_sharpe_proxy | -2.3043 |
| passes_zero_edge_after_haircut | False |
| positive_test_folds | 7 |
| severe_degradation_folds | 7 |
| full_matrix_pbo | 0.1429 |
| pbo_avg_oos_rank_pct | 0.8764 |
| trend_candle_oos_delta_pnl | 0.0000 |
| trend_candle_reduced_trades | 0 |

## Interpretation

The Donchian portfolio remains useful as a benchmark because PBO and
selected walk-forward evidence are not garbage. It is still not an active
alpha decision because the conservative Sharpe haircut/DSR proxy fails,
train/test degradation is severe, simple Binance carry produced zero
passing candidates, and the true entry-time trend/candle reducer found no
train-proven bad setup to exploit.

## Next Step

Run only a small predictive-funding research PoC if continuing. Do not
spend more engineering time on live execution gates until a new alpha path
has evidence after costs and walk-forward validation.
