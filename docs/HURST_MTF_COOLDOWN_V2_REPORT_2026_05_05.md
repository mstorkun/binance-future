# Hurst MTF Cooldown V2 Report - 2026-05-05

Status: research-only. This does not enable paper, testnet, or live execution.

Command: `python hurst_mtf_momentum_report.py --years 3 --folds 12 --train-bars 2400 --test-bars 300 --purge-bars 12 --loss-cooldown-bars 6 --out hurst_mtf_cooldown_v2_results.csv --matrix-out hurst_mtf_cooldown_v2_pbo_matrix.csv --trades-out hurst_mtf_cooldown_v2_trades.csv --json-out hurst_mtf_cooldown_v2_report.json --md-out docs/HURST_MTF_COOLDOWN_V2_REPORT_2026_05_05.md`

Strict status: `benchmark_only`

Methodology: fixed 8-perp universe, full 72-candidate grid unless
debug-capped by CLI, 12-fold train/test walk-forward, default 12-bar
purge gap before each test window, direction-specific 1h trigger volume
confirmation, severe cost stress, PBO matrix, concentration, tail-capture,
and crisis-alpha checks. Optional loss-cooldown variants block same-symbol
reentry after losing hard_stop/time_stop/regime_exit exits only when
`--loss-cooldown-bars` is greater than zero.

## Strict Gates

| gate | pass |
| --- | --- |
| net_cagr_after_severe_cost_pct | False |
| pbo_below_0_30 | False |
| walk_forward_positive_folds_7_of_12 | False |
| dsr_proxy_non_negative | False |
| sortino_at_least_2 | False |
| no_symbol_over_40_pct_pnl | True |
| no_month_over_25_pct_pnl | True |
| tail_capture_50_to_80_pct | False |
| crisis_alpha_positive | False |
| sample_at_least_200_trades | True |

## Severe Metrics

| total_return_pct | cagr_pct | max_dd_pct | sortino | sharpe | final_equity |
| --- | --- | --- | --- | --- | --- |
| -70.5401 | -52.4636 | 94.0126 | -0.3491 | -0.3239 | 1472.9954 |

## Concentration / Tail

| positive_folds | sample_trades | symbol_pnl_share | month_pnl_share | tail_capture | failed_checks |
| --- | --- | --- | --- | --- | --- |
| 4 | 381 | 0.0517 | 0.1221 | 0.4317 | net_cagr_after_severe_cost_pct,pbo_below_0_30,walk_forward_positive_folds_7_of_12,dsr_proxy_non_negative,sortino_at_least_2,tail_capture_50_to_80_pct,crisis_alpha_positive |

## Selected Candidates

| period | candidate | train_score | train_trades | train_return_pct | purge_bars | embargo_bars | loss_cooldown_bars | test_start | test_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | H0.58\|HX0.43\|ADX25\|VZ1.2\|TV0.60 | 7.085697 | 101 | 103.762274 | 12 | 0 | 6 | 2024-06-11T04:00:00+00:00 | 2024-07-31T00:00:00+00:00 |
| 2 | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 6.91408 | 210 | 96.662067 | 12 | 0 | 6 | 2024-07-31T04:00:00+00:00 | 2024-09-19T00:00:00+00:00 |
| 3 | H0.58\|HX0.43\|ADX25\|VZ1.2\|TV0.60 | 15.4688 | 159 | 311.972058 | 12 | 0 | 6 | 2024-09-19T04:00:00+00:00 | 2024-11-08T00:00:00+00:00 |
| 4 | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.60 | 9.905989 | 184 | 150.257068 | 12 | 0 | 6 | 2024-11-08T04:00:00+00:00 | 2024-12-28T00:00:00+00:00 |
| 5 | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.60 | 11.150575 | 231 | 205.929101 | 12 | 0 | 6 | 2024-12-28T04:00:00+00:00 | 2025-02-16T00:00:00+00:00 |
| 6 | H0.58\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 8.639552 | 270 | 131.74353 | 12 | 0 | 6 | 2025-02-16T04:00:00+00:00 | 2025-04-07T00:00:00+00:00 |
| 7 | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.45 | 3.866567 | 219 | 24.08112 | 12 | 0 | 6 | 2025-04-07T04:00:00+00:00 | 2025-05-27T00:00:00+00:00 |
| 8 | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 0.599086 | 197 | -16.436213 | 12 | 0 | 6 | 2025-05-27T04:00:00+00:00 | 2025-07-16T00:00:00+00:00 |
| 9 | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 3.487363 | 210 | 20.240696 | 12 | 0 | 6 | 2025-07-16T04:00:00+00:00 | 2025-09-04T00:00:00+00:00 |
| 10 | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.45 | 3.782978 | 221 | 25.226347 | 12 | 0 | 6 | 2025-09-04T04:00:00+00:00 | 2025-10-24T00:00:00+00:00 |
| 11 | H0.58\|HX0.45\|ADX20\|VZ1.5\|TV0.45 | -1.62269 | 306 | -33.800461 | 12 | 0 | 6 | 2025-10-24T04:00:00+00:00 | 2025-12-13T00:00:00+00:00 |
| 12 | H0.58\|HX0.45\|ADX20\|VZ1.5\|TV0.45 | -1.160245 | 283 | -29.515572 | 12 | 0 | 6 | 2025-12-13T04:00:00+00:00 | 2026-02-01T00:00:00+00:00 |

## Scenario Folds

| period | scenario | candidate | trades | total_return_pct | max_dd_pct | sortino | profit_factor | loss_cooldown_bars |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | baseline | H0.58\|HX0.43\|ADX25\|VZ1.2\|TV0.60 | 23 | -9.184548 | 16.519667 | -0.960088 | 0.771881 | 6 |
| 1 | slippage_30bps | H0.58\|HX0.43\|ADX25\|VZ1.2\|TV0.60 | 23 | -11.927573 | 16.760556 | -1.32868 | 0.710418 | 6 |
| 1 | slippage_60bps | H0.58\|HX0.43\|ADX25\|VZ1.2\|TV0.60 | 23 | -17.186533 | 20.023697 | -2.03711 | 0.601467 | 6 |
| 1 | funding_2x | H0.58\|HX0.43\|ADX25\|VZ1.2\|TV0.60 | 23 | -9.963405 | 16.549995 | -1.068536 | 0.754727 | 6 |
| 1 | severe | H0.58\|HX0.43\|ADX25\|VZ1.2\|TV0.60 | 23 | -17.903391 | 20.512562 | -2.143063 | 0.587855 | 6 |
| 2 | baseline | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 50 | 102.017761 | 46.266668 | 5.475411 | 1.638077 | 6 |
| 2 | slippage_30bps | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 50 | 91.227008 | 47.608467 | 5.162063 | 1.567143 | 6 |
| 2 | slippage_60bps | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 50 | 73.664705 | 49.802935 | 4.634807 | 1.45558 | 6 |
| 2 | funding_2x | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 50 | 99.445608 | 46.584367 | 5.403335 | 1.619395 | 6 |
| 2 | severe | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 50 | 71.435727 | 50.103231 | 4.562675 | 1.440301 | 6 |
| 3 | baseline | H0.58\|HX0.43\|ADX25\|VZ1.2\|TV0.60 | 51 | -38.495444 | 42.291357 | -4.741368 | 0.489381 | 6 |
| 3 | slippage_30bps | H0.58\|HX0.43\|ADX25\|VZ1.2\|TV0.60 | 51 | -43.231372 | 46.514472 | -5.495107 | 0.434342 | 6 |
| 3 | slippage_60bps | H0.58\|HX0.43\|ADX25\|VZ1.2\|TV0.60 | 50 | -51.929707 | 54.333232 | -7.008435 | 0.334568 | 6 |
| 3 | funding_2x | H0.58\|HX0.43\|ADX25\|VZ1.2\|TV0.60 | 51 | -39.933791 | 43.598069 | -4.971021 | 0.472597 | 6 |
| 3 | severe | H0.58\|HX0.43\|ADX25\|VZ1.2\|TV0.60 | 50 | -53.036669 | 55.35072 | -7.212155 | 0.323289 | 6 |
| 4 | baseline | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.60 | 45 | 37.725536 | 30.500569 | 2.232593 | 1.444156 | 6 |
| 4 | slippage_30bps | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.60 | 45 | 31.378726 | 31.883728 | 1.973755 | 1.368057 | 6 |
| 4 | slippage_60bps | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.60 | 45 | 19.484419 | 34.590523 | 1.478142 | 1.22743 | 6 |
| 4 | funding_2x | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.60 | 45 | 35.978934 | 30.900115 | 2.165084 | 1.422506 | 6 |
| 4 | severe | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.60 | 45 | 17.946952 | 34.974462 | 1.412466 | 1.209114 | 6 |
| 5 | baseline | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.60 | 28 | -16.26324 | 29.4117 | -1.087868 | 0.703955 | 6 |
| 5 | slippage_30bps | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.60 | 28 | -18.42772 | 30.293915 | -1.273097 | 0.668606 | 6 |
| 5 | slippage_60bps | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.60 | 28 | -22.60535 | 32.234999 | -1.626521 | 0.602968 | 6 |
| 5 | funding_2x | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.60 | 28 | -16.734574 | 29.588766 | -1.12802 | 0.696269 | 6 |
| 5 | severe | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.60 | 28 | -23.045174 | 32.535704 | -1.663126 | 0.59634 | 6 |
| 6 | baseline | H0.58\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 12 | -13.720594 | 20.760026 | -2.142678 | 0.337176 | 6 |
| 6 | slippage_30bps | H0.58\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 12 | -14.618372 | 21.417375 | -2.288245 | 0.311674 | 6 |
| 6 | slippage_60bps | H0.58\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 12 | -16.389776 | 22.718474 | -2.578541 | 0.270383 | 6 |
| 6 | funding_2x | H0.58\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 12 | -13.987953 | 20.949788 | -2.182022 | 0.330468 | 6 |
| 6 | severe | H0.58\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 12 | -16.650246 | 22.90449 | -2.614371 | 0.265724 | 6 |
| 7 | baseline | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.45 | 18 | -36.833292 | 38.860559 | -3.833007 | 0.175639 | 6 |
| 7 | slippage_30bps | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.45 | 18 | -38.061848 | 39.869222 | -3.992359 | 0.162191 | 6 |
| 7 | slippage_60bps | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.45 | 18 | -40.456846 | 41.844707 | -4.275488 | 0.137156 | 6 |
| 7 | funding_2x | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.45 | 18 | -37.178038 | 39.132974 | -3.865743 | 0.172419 | 6 |
| 7 | severe | H0.58\|HX0.43\|ADX25\|VZ1.5\|TV0.45 | 18 | -40.784833 | 42.106421 | -4.305302 | 0.134421 | 6 |
| 8 | baseline | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 41 | 8.541268 | 19.079927 | 1.113502 | 1.189792 | 6 |
| 8 | slippage_30bps | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 41 | 3.723113 | 19.609532 | 0.666407 | 1.080693 | 6 |
| 8 | slippage_60bps | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 41 | -5.322653 | 20.663488 | -0.190625 | 0.889552 | 6 |
| 8 | funding_2x | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 41 | 7.378587 | 19.177067 | 1.007784 | 1.162925 | 6 |
| 8 | severe | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 41 | -6.348577 | 20.868537 | -0.290581 | 0.868964 | 6 |
| 9 | baseline | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 27 | -5.409518 | 19.63803 | -0.420553 | 0.84105 | 6 |
| 9 | slippage_30bps | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 27 | -7.982398 | 20.964162 | -0.722133 | 0.770772 | 6 |
| 9 | slippage_60bps | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 27 | -12.937377 | 23.558366 | -1.314471 | 0.646067 | 6 |
| 9 | funding_2x | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 27 | -6.104518 | 20.057247 | -0.499988 | 0.82185 | 6 |
| 9 | severe | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 27 | -13.58258 | 23.959737 | -1.38894 | 0.631263 | 6 |
| 10 | baseline | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.45 | 13 | 4.584131 | 9.011872 | 0.968723 | 1.287579 | 6 |
| 10 | slippage_30bps | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.45 | 13 | 3.338949 | 9.611184 | 0.747552 | 1.202354 | 6 |
| 10 | slippage_60bps | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.45 | 13 | 0.888832 | 10.800352 | 0.314723 | 1.050503 | 6 |
| 10 | funding_2x | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.45 | 13 | 4.21592 | 9.180595 | 0.902283 | 1.261319 | 6 |
| 10 | severe | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.45 | 13 | 0.532321 | 10.966514 | 0.25129 | 1.029929 | 6 |
| 11 | baseline | H0.58\|HX0.45\|ADX20\|VZ1.5\|TV0.45 | 30 | -7.133499 | 13.027392 | -0.646935 | 0.739124 | 6 |
| 11 | slippage_30bps | H0.58\|HX0.45\|ADX20\|VZ1.5\|TV0.45 | 30 | -9.665927 | 13.919608 | -0.963082 | 0.658884 | 6 |
| 11 | slippage_60bps | H0.58\|HX0.45\|ADX20\|VZ1.5\|TV0.45 | 30 | -14.539164 | 15.774845 | -1.572214 | 0.521592 | 6 |
| 11 | funding_2x | H0.58\|HX0.45\|ADX20\|VZ1.5\|TV0.45 | 30 | -7.791582 | 13.225144 | -0.733067 | 0.717139 | 6 |
| 11 | severe | H0.58\|HX0.45\|ADX20\|VZ1.5\|TV0.45 | 30 | -15.149162 | 16.014059 | -1.653642 | 0.504716 | 6 |
| 12 | baseline | H0.58\|HX0.45\|ADX20\|VZ1.5\|TV0.45 | 44 | 70.468979 | 26.679089 | 6.11949 | 2.553456 | 6 |
| 12 | slippage_30bps | H0.58\|HX0.45\|ADX20\|VZ1.5\|TV0.45 | 44 | 61.846352 | 27.544249 | 5.4338 | 2.317178 | 6 |
| 12 | slippage_60bps | H0.58\|HX0.45\|ADX20\|VZ1.5\|TV0.45 | 44 | 45.799657 | 29.533589 | 4.183187 | 1.91079 | 6 |
| 12 | funding_2x | H0.58\|HX0.45\|ADX20\|VZ1.5\|TV0.45 | 44 | 68.526423 | 26.778126 | 5.981715 | 2.500729 | 6 |
| 12 | severe | H0.58\|HX0.45\|ADX20\|VZ1.5\|TV0.45 | 44 | 44.114795 | 29.884366 | 4.057081 | 1.871567 | 6 |

## Decision

Phase B is allowed only if every strict gate is true. If status is
`benchmark_only`, this candidate stays research-only and should be reviewed
before any further engineering work.
