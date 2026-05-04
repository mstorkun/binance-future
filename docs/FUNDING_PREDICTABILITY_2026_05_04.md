# Funding Predictability PoC - 2026-05-04

This is a research-only prediction report. It does not create a carry
executor, does not place orders, and does not change paper/testnet/live
behavior.

## Method

For each symbol, the signal is the rolling mean of already observed funding
prints. A threshold is learned on each train window; the test window then
checks whether high-signal periods have better future funding than the
unconditional test baseline.

Strict pass gate: at least `3` OOS folds, every fold must pass,
weighted OOS edge must be positive, and the selected sample count must meet
the per-fold minimum.

Command: `python funding_predictability_report.py --auto-universe --days 180 --signal-window 3 --horizon 3 --top-quantile 0.8 --train-samples 360 --test-samples 90 --min-folds 3`

## Result

- Symbols scanned: `42`
- Passing symbols: `0`
- Fold rows: `203`

| symbol | folds | ok_folds | selected_samples | avg_edge_vs_baseline_pct | avg_selected_annualized_apr_pct | avg_baseline_annualized_apr_pct | ok | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOT/USDT:USDT | 2 | 2.0000 | 25.0000 | 0.0544 | -4.8030 | -24.6776 | False | insufficient_oos_folds |
| WLD/USDT:USDT | 2 | 2.0000 | 31.0000 | 0.0528 | 3.3168 | -17.9268 | False | insufficient_oos_folds |
| AXL/USDT:USDT | 8 | 4.0000 | 146.0000 | 0.0451 | -7.2095 | -50.0587 | False | insufficient_oos_predictive_edge |
| BABY/USDT:USDT | 8 | 7.0000 | 275.0000 | 0.0274 | 2.2837 | -8.2421 | False | insufficient_oos_predictive_edge |
| ZEC/USDT:USDT | 2 | 0.0000 | 12.0000 | 0.0185 | 4.0667 | -2.5587 | False | insufficient_oos_folds |
| TAO/USDT:USDT | 8 | 6.0000 | 143.0000 | 0.0159 | 0.3962 | -5.8274 | False | insufficient_oos_predictive_edge |
| BIO/USDT:USDT | 14 | 10.0000 | 434.0000 | 0.0155 | -0.8590 | -15.7021 | False | insufficient_oos_predictive_edge |
| DASH/USDT:USDT | 2 | 2.0000 | 45.0000 | 0.0141 | 3.0955 | -1.9434 | False | insufficient_oos_folds |
| BTC/USDT:USDT | 2 | 0.0000 | 1.0000 | 0.0126 | 1.9944 | -1.8558 | False | insufficient_oos_folds |
| ORCA/USDT:USDT | 19 | 12.0000 | 553.0000 | 0.0109 | -5.1787 | -54.8222 | False | insufficient_oos_predictive_edge |
| WLFI/USDT:USDT | 8 | 7.0000 | 271.0000 | 0.0072 | 2.5095 | -6.8995 | False | insufficient_oos_predictive_edge |
| ETH/USDT:USDT | 2 | 0.0000 | 12.0000 | 0.0067 | 1.1026 | -1.2174 | False | insufficient_oos_folds |

## Decision

A pass here would not be live or executor approval; it would only mean a
symbol deserves deeper research with costs, borrow/transfer constraints,
liquidity, and walk-forward model stability. Pass count is zero under the
strict gate, so do not build a funding executor from this PoC.
