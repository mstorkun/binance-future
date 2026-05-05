# HTF Support/Resistance Reversion Report - 2026-05-05

Status: research-only. This does not enable paper, testnet, or live execution.

Command: `python htf_reversion_report.py --years 3 --folds 12 --train-bars 2400 --test-bars 300 --purge-bars 12 --out htf_reversion_results.csv --matrix-out htf_reversion_pbo_matrix.csv --trades-out htf_reversion_trades.csv --json-out htf_reversion_report.json --md-out docs/HTF_REVERSION_REPORT_2026_05_05.md`

Strict status: `benchmark_only`

Methodology: fixed 8-perp universe, 4h entries, prior 4h support/resistance
levels shifted to the next bar, RSI exhaustion, low-ADX range filter, optional
volume exhaustion, 12-fold train/test walk-forward, purge gap, severe cost
stress, PBO matrix, concentration, tail-capture, and crisis-alpha checks.

## Strict Gates

| gate | pass |
| --- | --- |
| net_cagr_after_severe_cost_pct | False |
| pbo_below_0_30 | False |
| walk_forward_positive_folds_7_of_12 | False |
| dsr_proxy_non_negative | False |
| sortino_at_least_2 | False |
| no_symbol_over_40_pct_pnl | True |
| no_month_over_25_pct_pnl | False |
| tail_capture_50_to_80_pct | False |
| crisis_alpha_positive | False |
| sample_at_least_200_trades | False |

## Severe Metrics

| total_return_pct | cagr_pct | max_dd_pct | sortino | sharpe | final_equity |
| --- | --- | --- | --- | --- | --- |
| -2.0765 | -1.2687 | 11.4489 | -0.0265 | -0.1179 | 4896.1768 |

## Concentration / Tail

| positive_folds | sample_trades | symbol_pnl_share | month_pnl_share | tail_capture | failed_checks |
| --- | --- | --- | --- | --- | --- |
| 5 | 31 | 0.2152 | 0.2544 | 0.1598 | net_cagr_after_severe_cost_pct,pbo_below_0_30,walk_forward_positive_folds_7_of_12,dsr_proxy_non_negative,sortino_at_least_2,no_month_over_25_pct_pnl,tail_capture_50_to_80_pct,crisis_alpha_positive,sample_at_least_200_trades |

## Selected Candidates

| period | candidate | train_score | train_trades | train_return_pct | purge_bars | embargo_bars | test_start | test_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | LB60\|RSI35-65\|ADX18\|T0.50\|R1.5\|TV0.35\|VZ0.0\|AVD1 | 0.346273 | 30 | 1.174269 | 12 | 0 | 2024-06-11T04:00:00+00:00 | 2024-07-31T00:00:00+00:00 |
| 2 | LB120\|RSI35-65\|ADX18\|T0.50\|R1.5\|TV0.50\|VZ0.0\|AVD1 | 0.240948 | 20 | 1.015095 | 12 | 0 | 2024-07-31T04:00:00+00:00 | 2024-09-19T00:00:00+00:00 |
| 3 | LB180\|RSI35-65\|ADX26\|T0.25\|R1.5\|TV0.50\|VZ1.0\|AVD1 | -2.320172 | 22 | -19.788017 | 12 | 0 | 2024-09-19T04:00:00+00:00 | 2024-11-08T00:00:00+00:00 |
| 4 | LB120\|RSI35-65\|ADX26\|T0.00\|R1.5\|TV0.35\|VZ1.0\|AVD1 | -1.109295 | 31 | -7.557536 | 12 | 0 | 2024-11-08T04:00:00+00:00 | 2024-12-28T00:00:00+00:00 |
| 5 | LB60\|RSI35-65\|ADX22\|T0.50\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 0.620868 | 23 | 2.349072 | 12 | 0 | 2024-12-28T04:00:00+00:00 | 2025-02-16T00:00:00+00:00 |
| 6 | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1.344846 | 21 | 4.875644 | 12 | 0 | 2025-02-16T04:00:00+00:00 | 2025-04-07T00:00:00+00:00 |
| 7 | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1.724329 | 26 | 5.948119 | 12 | 0 | 2025-04-07T04:00:00+00:00 | 2025-05-27T00:00:00+00:00 |
| 8 | LB60\|RSI30-70\|ADX26\|T0.50\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 0.463171 | 21 | 2.057944 | 12 | 0 | 2025-05-27T04:00:00+00:00 | 2025-07-16T00:00:00+00:00 |
| 9 | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1.103708 | 30 | 3.444803 | 12 | 0 | 2025-07-16T04:00:00+00:00 | 2025-09-04T00:00:00+00:00 |
| 10 | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 0.447082 | 31 | 1.254981 | 12 | 0 | 2025-09-04T04:00:00+00:00 | 2025-10-24T00:00:00+00:00 |
| 11 | LB60\|RSI35-65\|ADX22\|T0.00\|R1.5\|TV0.35\|VZ0.0\|AVD1 | 0.907271 | 25 | 2.626948 | 12 | 0 | 2025-10-24T04:00:00+00:00 | 2025-12-13T00:00:00+00:00 |
| 12 | LB60\|RSI35-65\|ADX22\|T0.00\|R1.5\|TV0.50\|VZ0.0\|AVD1 | 5.265549 | 22 | 16.723362 | 12 | 0 | 2025-12-13T04:00:00+00:00 | 2026-02-01T00:00:00+00:00 |

## Scenario Folds

| period | scenario | candidate | trades | total_return_pct | max_dd_pct | sortino | profit_factor |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | baseline | LB60\|RSI35-65\|ADX18\|T0.50\|R1.5\|TV0.35\|VZ0.0\|AVD1 | 0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 1 | slippage_30bps | LB60\|RSI35-65\|ADX18\|T0.50\|R1.5\|TV0.35\|VZ0.0\|AVD1 | 0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 1 | slippage_60bps | LB60\|RSI35-65\|ADX18\|T0.50\|R1.5\|TV0.35\|VZ0.0\|AVD1 | 0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 1 | funding_2x | LB60\|RSI35-65\|ADX18\|T0.50\|R1.5\|TV0.35\|VZ0.0\|AVD1 | 0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 1 | severe | LB60\|RSI35-65\|ADX18\|T0.50\|R1.5\|TV0.35\|VZ0.0\|AVD1 | 0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 2 | baseline | LB120\|RSI35-65\|ADX18\|T0.50\|R1.5\|TV0.50\|VZ0.0\|AVD1 | 1 | 1.494433 | 0.928645 | 0.0 | 74.7216 |
| 2 | slippage_30bps | LB120\|RSI35-65\|ADX18\|T0.50\|R1.5\|TV0.50\|VZ0.0\|AVD1 | 1 | 1.420393 | 0.928988 | 0.0 | 71.0197 |
| 2 | slippage_60bps | LB120\|RSI35-65\|ADX18\|T0.50\|R1.5\|TV0.50\|VZ0.0\|AVD1 | 1 | 1.272314 | 0.929675 | 0.0 | 63.6157 |
| 2 | funding_2x | LB120\|RSI35-65\|ADX18\|T0.50\|R1.5\|TV0.50\|VZ0.0\|AVD1 | 1 | 1.477157 | 0.928645 | 0.0 | 73.8578 |
| 2 | severe | LB120\|RSI35-65\|ADX18\|T0.50\|R1.5\|TV0.50\|VZ0.0\|AVD1 | 1 | 1.25504 | 0.929675 | 0.0 | 62.7519 |
| 3 | baseline | LB180\|RSI35-65\|ADX26\|T0.25\|R1.5\|TV0.50\|VZ1.0\|AVD1 | 4 | 3.026355 | 3.55352 | 0.30649 | 1.834224 |
| 3 | slippage_30bps | LB180\|RSI35-65\|ADX26\|T0.25\|R1.5\|TV0.50\|VZ1.0\|AVD1 | 4 | 2.523336 | 3.673185 | 0.249606 | 1.673653 |
| 3 | slippage_60bps | LB180\|RSI35-65\|ADX26\|T0.25\|R1.5\|TV0.50\|VZ1.0\|AVD1 | 4 | 1.522814 | 3.912511 | 0.146646 | 1.382526 |
| 3 | funding_2x | LB180\|RSI35-65\|ADX26\|T0.25\|R1.5\|TV0.50\|VZ1.0\|AVD1 | 4 | 2.956512 | 3.557509 | 0.299372 | 1.814118 |
| 3 | severe | LB180\|RSI35-65\|ADX26\|T0.25\|R1.5\|TV0.50\|VZ1.0\|AVD1 | 4 | 1.453722 | 3.916501 | 0.140372 | 1.364826 |
| 4 | baseline | LB120\|RSI35-65\|ADX26\|T0.00\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1 | -3.181883 | 3.337366 | -0.927584 | 0.0 |
| 4 | slippage_30bps | LB120\|RSI35-65\|ADX26\|T0.00\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1 | -3.231432 | 3.362932 | -0.912115 | 0.0 |
| 4 | slippage_60bps | LB120\|RSI35-65\|ADX26\|T0.00\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1 | -3.330535 | 3.414106 | -0.883935 | 0.0 |
| 4 | funding_2x | LB120\|RSI35-65\|ADX26\|T0.00\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1 | -3.186837 | 3.342312 | -0.922984 | 0.0 |
| 4 | severe | LB120\|RSI35-65\|ADX26\|T0.00\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1 | -3.335489 | 3.419056 | -0.880004 | 0.0 |
| 5 | baseline | LB60\|RSI35-65\|ADX22\|T0.50\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 4 | -0.485191 | 2.707853 | -0.172193 | 0.700831 |
| 5 | slippage_30bps | LB60\|RSI35-65\|ADX22\|T0.50\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 4 | -0.665564 | 2.813233 | -0.235678 | 0.598271 |
| 5 | slippage_60bps | LB60\|RSI35-65\|ADX22\|T0.50\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 4 | -1.025629 | 3.023865 | -0.375376 | 0.472944 |
| 5 | funding_2x | LB60\|RSI35-65\|ADX22\|T0.50\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 4 | -0.520851 | 2.741616 | -0.182713 | 0.674897 |
| 5 | severe | LB60\|RSI35-65\|ADX22\|T0.50\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 4 | -1.061174 | 3.057594 | -0.390789 | 0.462637 |
| 6 | baseline | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 4 | 0.505679 | 1.9689 | 0.281623 | 1.368134 |
| 6 | slippage_30bps | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 4 | 0.265295 | 2.019063 | 0.154295 | 1.180176 |
| 6 | slippage_60bps | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 4 | -0.214511 | 2.119543 | -0.089853 | 0.871484 |
| 6 | funding_2x | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 4 | 0.446924 | 2.006761 | 0.252173 | 1.316481 |
| 6 | severe | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 4 | -0.273044 | 2.157462 | -0.119217 | 0.840088 |
| 7 | baseline | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 3 | -3.383021 | 4.463718 | -1.199284 | 0.250584 |
| 7 | slippage_30bps | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 3 | -3.764993 | 4.791742 | -1.232109 | 0.222658 |
| 7 | slippage_60bps | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 3 | -4.526194 | 5.446099 | -1.274415 | 0.176919 |
| 7 | funding_2x | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 3 | -3.401334 | 4.480165 | -1.196024 | 0.249281 |
| 7 | severe | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 3 | -4.544377 | 5.462461 | -1.273021 | 0.176073 |
| 8 | baseline | LB60\|RSI30-70\|ADX26\|T0.50\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1 | 1.34976 | 1.567031 | 0.412322 | 67.488 |
| 8 | slippage_30bps | LB60\|RSI30-70\|ADX26\|T0.50\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1 | 1.281676 | 1.601073 | 0.387017 | 64.0838 |
| 8 | slippage_60bps | LB60\|RSI30-70\|ADX26\|T0.50\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1 | 1.145507 | 1.669157 | 0.337207 | 57.2753 |
| 8 | funding_2x | LB60\|RSI30-70\|ADX26\|T0.50\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1 | 1.331604 | 1.567031 | 0.406906 | 66.5802 |
| 8 | severe | LB60\|RSI30-70\|ADX26\|T0.50\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 1 | 1.127351 | 1.669157 | 0.332012 | 56.3675 |
| 9 | baseline | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 2 | -1.197568 | 3.002855 | -0.233577 | 0.60119 |
| 9 | slippage_30bps | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 2 | -1.432332 | 3.177133 | -0.283312 | 0.549175 |
| 9 | slippage_60bps | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 2 | -1.901244 | 3.525691 | -0.381143 | 0.460746 |
| 9 | funding_2x | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 2 | -1.232702 | 3.026091 | -0.240921 | 0.592642 |
| 9 | severe | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 2 | -1.936277 | 3.548927 | -0.388159 | 0.454405 |
| 10 | baseline | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 10 | slippage_30bps | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 10 | slippage_60bps | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 10 | funding_2x | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 10 | severe | LB60\|RSI35-65\|ADX22\|T0.25\|R1.5\|TV0.35\|VZ1.0\|AVD1 | 0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 11 | baseline | LB60\|RSI35-65\|ADX22\|T0.00\|R1.5\|TV0.35\|VZ0.0\|AVD1 | 4 | 5.641004 | 0.200267 | 12.607305 | 282.0501 |
| 11 | slippage_30bps | LB60\|RSI35-65\|ADX22\|T0.00\|R1.5\|TV0.35\|VZ0.0\|AVD1 | 4 | 5.349214 | 0.235281 | 7.961137 | 267.4607 |
| 11 | slippage_60bps | LB60\|RSI35-65\|ADX22\|T0.00\|R1.5\|TV0.35\|VZ0.0\|AVD1 | 4 | 4.767043 | 0.305309 | 6.672109 | 238.3522 |
| 11 | funding_2x | LB60\|RSI35-65\|ADX22\|T0.00\|R1.5\|TV0.35\|VZ0.0\|AVD1 | 4 | 5.607057 | 0.200267 | 12.533832 | 280.3528 |
| 11 | severe | LB60\|RSI35-65\|ADX22\|T0.00\|R1.5\|TV0.35\|VZ0.0\|AVD1 | 4 | 4.733255 | 0.305309 | 6.7971 | 236.6629 |
| 12 | baseline | LB60\|RSI35-65\|ADX22\|T0.00\|R1.5\|TV0.50\|VZ0.0\|AVD1 | 7 | 3.576666 | 5.053876 | 0.911805 | 1.67528 |
| 12 | slippage_30bps | LB60\|RSI35-65\|ADX22\|T0.00\|R1.5\|TV0.50\|VZ0.0\|AVD1 | 7 | 2.685538 | 5.344106 | 0.666845 | 1.481073 |
| 12 | slippage_60bps | LB60\|RSI35-65\|ADX22\|T0.00\|R1.5\|TV0.50\|VZ0.0\|AVD1 | 7 | 0.922217 | 5.923319 | 0.229228 | 1.150031 |
| 12 | funding_2x | LB60\|RSI35-65\|ADX22\|T0.00\|R1.5\|TV0.50\|VZ0.0\|AVD1 | 7 | 3.459508 | 5.105988 | 0.880151 | 1.646683 |
| 12 | severe | LB60\|RSI35-65\|ADX22\|T0.00\|R1.5\|TV0.50\|VZ0.0\|AVD1 | 7 | 0.807525 | 5.975245 | 0.203212 | 1.130269 |

## Decision

Phase B is allowed only if every strict gate is true. If status is
`benchmark_only`, this candidate stays research-only and should not be
connected to paper or live execution.
