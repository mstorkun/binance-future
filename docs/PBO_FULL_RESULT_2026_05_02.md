# Full PBO Matrix Result 2026-05-02

Status: completes the first full candidate-by-fold PBO run for the current
DOGE/LINK/TRX risk-capped parameter universe. This does not approve live
trading.

## Command

```bash
python portfolio_param_walk_forward.py --years 3 --train-bars 3000 --test-bars 500 --roll-bars 500 --risk-capped --out pbo_full_wf.csv --matrix-out portfolio_param_candidate_matrix.csv
python pbo_report.py --matrix portfolio_param_candidate_matrix.csv --out pbo_report.json
```

Runtime:

- Full matrix job wall time: about 61.5 minutes.
- Symbols: `DOGE/USDT`, `LINK/USDT`, `TRX/USDT`
- Candidate universe: `216` candidates per fold.
- Folds: `7`

Committed artifacts:

- [PBO_FULL_REPORT_2026_05_02.json](PBO_FULL_REPORT_2026_05_02.json)
- [PBO_SELECTED_WF_2026_05_02.csv](PBO_SELECTED_WF_2026_05_02.csv)
- [PBO_CANDIDATE_MATRIX_2026_05_02.csv](PBO_CANDIDATE_MATRIX_2026_05_02.csv)

## PBO Summary

| Metric | Value |
|---|---:|
| Folds | 7 |
| Candidates per fold | 216 |
| PBO | 0.1429 |
| Average OOS rank percentile | 0.8764 |
| Median OOS rank percentile | 0.9860 |
| Selected folds in OOS top half | 6 / 7 |
| Positive selected test folds | 7 / 7 |
| Average selected test return | 24.86% |
| Worst selected test drawdown | 6.08% |

## Selected Fold Results

| Fold | Selected candidate | Test return | Test DD | OOS rank | OOS rank pct | PBO hit |
|---:|---|---:|---:|---:|---:|---|
| 1 | `growth_70_compound|D15|DX8|VOL1.2|SL1.5` | 43.68% | 2.95% | 1 / 216 | 1.0000 | false |
| 2 | `growth_70_compound|D15|DX8|VOL1.2|SL1.5` | 47.23% | 4.24% | 4 / 216 | 0.9860 | false |
| 3 | `growth_70_compound|D15|DX8|VOL1.2|SL1.5` | 20.61% | 4.62% | 4 / 216 | 0.9860 | false |
| 4 | `growth_70_compound|D15|DX8|VOL1.2|SL1.5` | 23.58% | 3.89% | 1 / 216 | 1.0000 | false |
| 5 | `growth_70_compound|D15|DX8|VOL1.2|SL1.5` | 23.03% | 6.08% | 113 / 216 | 0.4791 | true |
| 6 | `growth_70_compound|D15|DX8|VOL1.2|SL2.0` | 10.45% | 5.13% | 11 / 216 | 0.9535 | false |
| 7 | `growth_70_compound|D15|DX8|VOL1.5|SL2.0` | 5.42% | 5.05% | 59 / 216 | 0.7302 | false |

## Interpretation

This is materially stronger than the earlier selected-row proxy. The full matrix
shows the train-selected candidate usually remains near the top of the
out-of-sample candidate universe.

The result still does not approve live trading:

- The test universe is still built around the chosen DOGE/LINK/TRX portfolio.
- Cost, liquidity shock, funding shock, and real fill quality remain live
  blockers.
- User-data stream websocket runner and event ordering are still missing.
- `LIVE_TRADING_APPROVED=False` and `USER_DATA_STREAM_READY=False` remain the
  correct runtime state.

## Verification

- `python portfolio_param_walk_forward.py --years 3 --train-bars 3000 --test-bars 500 --roll-bars 500 --risk-capped --out pbo_full_wf.csv --matrix-out portfolio_param_candidate_matrix.csv`
- `python pbo_report.py --matrix portfolio_param_candidate_matrix.csv --out pbo_report.json`
