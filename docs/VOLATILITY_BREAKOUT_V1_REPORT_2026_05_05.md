# Volatility Breakout V1 Report - 2026-05-05

Status: research-only. This does not enable paper, testnet, or live execution.

Command: `python volatility_breakout_report.py --years 3 --folds 12 --train-bars 9600 --test-bars 1200 --purge-bars 36 --out volatility_breakout_v1_results.csv --matrix-out volatility_breakout_v1_pbo_matrix.csv --trades-out volatility_breakout_v1_trades.csv --json-out volatility_breakout_v1_report.json --md-out docs/VOLATILITY_BREAKOUT_V1_REPORT_2026_05_05.md`

Strict status: `benchmark_only`

Methodology: fixed 8-perp universe, 1h entries, recent Bollinger-bandwidth
squeeze, volume-confirmed 1h range breakout, 4h trend/ADX alignment, BTC
market-leader direction gate, 12-fold train/test walk-forward, purge gap,
severe cost stress, PBO matrix, concentration, tail-capture, and crisis-alpha checks.

## Strict Gates

| gate | pass |
| --- | --- |
| net_cagr_after_severe_cost_pct | False |
| pbo_below_0_30 | False |
| walk_forward_positive_folds_7_of_12 | False |
| dsr_proxy_non_negative | False |
| sortino_at_least_2 | False |
| no_symbol_over_40_pct_pnl | False |
| no_month_over_25_pct_pnl | True |
| tail_capture_50_to_80_pct | False |
| crisis_alpha_positive | False |
| sample_at_least_200_trades | True |

## Severe Metrics

| total_return_pct | cagr_pct | max_dd_pct | sortino | sharpe | final_equity |
| --- | --- | --- | --- | --- | --- |
| -73.2745 | -55.1919 | 75.2624 | -1.2828 | -2.8492 | 1336.2772 |

## Concentration / Tail

| positive_folds | sample_trades | symbol_pnl_share | month_pnl_share | tail_capture | failed_checks |
| --- | --- | --- | --- | --- | --- |
| 1 | 296 | 1.0 | 0.1504 | 0.3302 | net_cagr_after_severe_cost_pct,pbo_below_0_30,walk_forward_positive_folds_7_of_12,dsr_proxy_non_negative,sortino_at_least_2,no_symbol_over_40_pct_pnl,tail_capture_50_to_80_pct,crisis_alpha_positive |

## Selected Candidates

| period | candidate | train_score | train_trades | train_return_pct | purge_bars | embargo_bars | test_start | test_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | BO24\|SQ120-0.35\|VZ1.8\|ADX20\|TV0.45 | 11.15326 | 304 | 103.535602 | 36 | 0 | 2024-06-10T20:00:00+00:00 | 2024-07-30T19:00:00+00:00 |
| 2 | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 0.334946 | 128 | 0.711019 | 36 | 0 | 2024-07-30T20:00:00+00:00 | 2024-09-18T19:00:00+00:00 |
| 3 | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | -0.562299 | 140 | -5.499919 | 36 | 0 | 2024-09-18T20:00:00+00:00 | 2024-11-07T19:00:00+00:00 |
| 4 | BO72\|SQ120-0.35\|VZ1.8\|ADX20\|TV0.45 | 0.294332 | 259 | -2.632448 | 36 | 0 | 2024-11-07T20:00:00+00:00 | 2024-12-27T19:00:00+00:00 |
| 5 | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | -2.484267 | 146 | -22.421428 | 36 | 0 | 2024-12-27T20:00:00+00:00 | 2025-02-15T19:00:00+00:00 |
| 6 | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | -2.701057 | 154 | -24.771507 | 36 | 0 | 2025-02-15T20:00:00+00:00 | 2025-04-06T19:00:00+00:00 |
| 7 | BO72\|SQ120-0.25\|VZ1.8\|ADX20\|TV0.45 | -2.327902 | 210 | -31.059266 | 36 | 0 | 2025-04-06T20:00:00+00:00 | 2025-05-26T19:00:00+00:00 |
| 8 | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | -1.132297 | 154 | -12.498061 | 36 | 0 | 2025-05-26T20:00:00+00:00 | 2025-07-15T19:00:00+00:00 |
| 9 | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | -0.497085 | 160 | -6.941866 | 36 | 0 | 2025-07-15T20:00:00+00:00 | 2025-09-03T19:00:00+00:00 |
| 10 | BO72\|SQ240-0.15\|VZ1.2\|ADX15\|TV0.45 | -1.368541 | 267 | -16.650182 | 36 | 0 | 2025-09-03T20:00:00+00:00 | 2025-10-23T19:00:00+00:00 |
| 11 | BO72\|SQ120-0.15\|VZ1.8\|ADX15\|TV0.45 | -1.22777 | 213 | -11.701318 | 36 | 0 | 2025-10-23T20:00:00+00:00 | 2025-12-12T19:00:00+00:00 |
| 12 | BO72\|SQ240-0.15\|VZ1.8\|ADX15\|TV0.45 | -0.163174 | 196 | -3.979203 | 36 | 0 | 2025-12-12T20:00:00+00:00 | 2026-01-31T19:00:00+00:00 |

## Scenario Folds

| period | scenario | candidate | trades | total_return_pct | max_dd_pct | sortino | profit_factor |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | baseline | BO24\|SQ120-0.35\|VZ1.8\|ADX20\|TV0.45 | 35 | -1.688946 | 7.277114 | -0.206286 | 0.923528 |
| 1 | slippage_30bps | BO24\|SQ120-0.35\|VZ1.8\|ADX20\|TV0.45 | 35 | -5.187083 | 9.583971 | -0.818947 | 0.778922 |
| 1 | slippage_60bps | BO24\|SQ120-0.35\|VZ1.8\|ADX20\|TV0.45 | 35 | -11.834852 | 14.041921 | -1.939008 | 0.53872 |
| 1 | funding_2x | BO24\|SQ120-0.35\|VZ1.8\|ADX20\|TV0.45 | 35 | -1.94205 | 7.458448 | -0.250912 | 0.9127 |
| 1 | severe | BO24\|SQ120-0.35\|VZ1.8\|ADX20\|TV0.45 | 35 | -12.063348 | 14.211167 | -1.975824 | 0.532071 |
| 2 | baseline | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 25 | -9.919578 | 15.598358 | -0.861646 | 0.52405 |
| 2 | slippage_30bps | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 25 | -12.005828 | 17.038779 | -1.044797 | 0.442453 |
| 2 | slippage_60bps | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 25 | -16.047621 | 19.943772 | -1.393025 | 0.301506 |
| 2 | funding_2x | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 25 | -10.054973 | 15.658998 | -0.8748 | 0.518102 |
| 2 | severe | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 25 | -16.174564 | 20.012146 | -1.405317 | 0.297626 |
| 3 | baseline | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 16 | -10.846235 | 10.971657 | -2.401474 | 0.279477 |
| 3 | slippage_30bps | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 16 | -12.58871 | 12.65364 | -2.698348 | 0.214208 |
| 3 | slippage_60bps | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 16 | -15.980428 | 15.980428 | -3.184696 | 0.128209 |
| 3 | funding_2x | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 16 | -10.947609 | 11.072888 | -2.42174 | 0.275149 |
| 3 | severe | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 16 | -16.076446 | 16.076446 | -3.201104 | 0.125813 |
| 4 | baseline | BO72\|SQ120-0.35\|VZ1.8\|ADX20\|TV0.45 | 45 | -16.894934 | 19.483524 | -1.59036 | 0.596704 |
| 4 | slippage_30bps | BO72\|SQ120-0.35\|VZ1.8\|ADX20\|TV0.45 | 45 | -19.578087 | 21.389636 | -1.861131 | 0.541925 |
| 4 | slippage_60bps | BO72\|SQ120-0.35\|VZ1.8\|ADX20\|TV0.45 | 45 | -24.696911 | 25.212767 | -2.393971 | 0.442727 |
| 4 | funding_2x | BO72\|SQ120-0.35\|VZ1.8\|ADX20\|TV0.45 | 45 | -17.086141 | 19.614411 | -1.608835 | 0.593103 |
| 4 | severe | BO72\|SQ120-0.35\|VZ1.8\|ADX20\|TV0.45 | 45 | -24.871103 | 25.33665 | -2.410316 | 0.439915 |
| 5 | baseline | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 15 | -1.242018 | 8.122414 | -0.129276 | 0.86405 |
| 5 | slippage_30bps | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 15 | -2.302627 | 8.795463 | -0.253531 | 0.759058 |
| 5 | slippage_60bps | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 15 | -4.39377 | 10.129713 | -0.475934 | 0.580829 |
| 5 | funding_2x | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 15 | -1.313512 | 8.179675 | -0.138181 | 0.85689 |
| 5 | severe | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 15 | -4.463294 | 10.185982 | -0.486837 | 0.576061 |
| 6 | baseline | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 18 | 8.381346 | 5.494884 | 1.646344 | 1.976457 |
| 6 | slippage_30bps | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 18 | 7.045491 | 5.660491 | 1.348021 | 1.764924 |
| 6 | slippage_60bps | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 18 | 4.418049 | 6.000251 | 0.814233 | 1.38959 |
| 6 | funding_2x | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 18 | 8.326542 | 5.500909 | 1.638071 | 1.966126 |
| 6 | severe | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 18 | 4.365088 | 6.010741 | 0.805759 | 1.382565 |
| 7 | baseline | BO72\|SQ120-0.25\|VZ1.8\|ADX20\|TV0.45 | 21 | 4.367355 | 11.406201 | 0.892799 | 1.269519 |
| 7 | slippage_30bps | BO72\|SQ120-0.25\|VZ1.8\|ADX20\|TV0.45 | 21 | 2.417237 | 12.571583 | 0.55013 | 1.14264 |
| 7 | slippage_60bps | BO72\|SQ120-0.25\|VZ1.8\|ADX20\|TV0.45 | 21 | -1.382352 | 14.860586 | -0.110827 | 0.925332 |
| 7 | funding_2x | BO72\|SQ120-0.25\|VZ1.8\|ADX20\|TV0.45 | 21 | 4.215433 | 11.506742 | 0.86665 | 1.259126 |
| 7 | severe | BO72\|SQ120-0.25\|VZ1.8\|ADX20\|TV0.45 | 21 | -1.526518 | 14.957584 | -0.135934 | 0.917869 |
| 8 | baseline | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 19 | 1.766666 | 6.098672 | 0.452939 | 1.141694 |
| 8 | slippage_30bps | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 19 | -0.45826 | 6.444249 | -0.026259 | 0.965797 |
| 8 | slippage_60bps | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 19 | -4.776068 | 7.880459 | -0.876421 | 0.685543 |
| 8 | funding_2x | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 19 | 1.58252 | 6.122588 | 0.413205 | 1.1259 |
| 8 | severe | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 19 | -4.949403 | 7.948245 | -0.90889 | 0.676145 |
| 9 | baseline | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 24 | -3.418471 | 7.109191 | -0.484526 | 0.788471 |
| 9 | slippage_30bps | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 24 | -5.671889 | 8.606688 | -0.819778 | 0.668236 |
| 9 | slippage_60bps | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 24 | -10.033141 | 11.628716 | -1.418621 | 0.472543 |
| 9 | funding_2x | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 24 | -3.57745 | 7.20281 | -0.509675 | 0.779344 |
| 9 | severe | BO72\|SQ240-0.15\|VZ1.8\|ADX20\|TV0.45 | 24 | -10.182056 | 11.718245 | -1.44023 | 0.46647 |
| 10 | baseline | BO72\|SQ240-0.15\|VZ1.2\|ADX15\|TV0.45 | 44 | -13.677799 | 22.078168 | -1.879549 | 0.605921 |
| 10 | slippage_30bps | BO72\|SQ240-0.15\|VZ1.2\|ADX15\|TV0.45 | 44 | -17.982408 | 24.02169 | -2.495543 | 0.502159 |
| 10 | slippage_60bps | BO72\|SQ240-0.15\|VZ1.2\|ADX15\|TV0.45 | 44 | -25.988216 | 27.778693 | -3.617025 | 0.332377 |
| 10 | funding_2x | BO72\|SQ240-0.15\|VZ1.2\|ADX15\|TV0.45 | 44 | -14.020348 | 22.230219 | -1.930551 | 0.597282 |
| 10 | severe | BO72\|SQ240-0.15\|VZ1.2\|ADX15\|TV0.45 | 44 | -26.285564 | 27.921672 | -3.661468 | 0.326288 |
| 11 | baseline | BO72\|SQ120-0.15\|VZ1.8\|ADX15\|TV0.45 | 15 | 0.59849 | 5.670679 | 0.150828 | 1.060984 |
| 11 | slippage_30bps | BO72\|SQ120-0.15\|VZ1.8\|ADX15\|TV0.45 | 15 | -0.854852 | 6.076343 | -0.078697 | 0.918662 |
| 11 | slippage_60bps | BO72\|SQ120-0.15\|VZ1.8\|ADX15\|TV0.45 | 15 | -3.705288 | 6.88395 | -0.478074 | 0.699836 |
| 11 | funding_2x | BO72\|SQ120-0.15\|VZ1.8\|ADX15\|TV0.45 | 15 | 0.515517 | 5.70419 | 0.137431 | 1.052307 |
| 11 | severe | BO72\|SQ120-0.15\|VZ1.8\|ADX15\|TV0.45 | 15 | -3.785048 | 6.917114 | -0.489408 | 0.694563 |
| 12 | baseline | BO72\|SQ240-0.15\|VZ1.8\|ADX15\|TV0.45 | 19 | 3.639683 | 8.354846 | 0.488294 | 1.292115 |
| 12 | slippage_30bps | BO72\|SQ240-0.15\|VZ1.8\|ADX15\|TV0.45 | 19 | 1.332861 | 8.780352 | 0.203531 | 1.092765 |
| 12 | slippage_60bps | BO72\|SQ240-0.15\|VZ1.8\|ADX15\|TV0.45 | 19 | -3.142794 | 10.815992 | -0.310998 | 0.770716 |
| 12 | funding_2x | BO72\|SQ240-0.15\|VZ1.8\|ADX15\|TV0.45 | 19 | 3.497468 | 8.383367 | 0.470761 | 1.279527 |
| 12 | severe | BO72\|SQ240-0.15\|VZ1.8\|ADX15\|TV0.45 | 19 | -3.276492 | 10.881069 | -0.326004 | 0.762271 |

## Decision

Phase B is allowed only if every strict gate is true. If status is
`benchmark_only`, this candidate stays research-only and should not be
connected to paper or live execution.
