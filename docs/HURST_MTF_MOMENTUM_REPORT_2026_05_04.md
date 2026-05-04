# Hurst MTF Momentum Phase A Report - 2026-05-04

Status: research-only. This does not enable paper, testnet, or live execution.

Command: `python hurst_mtf_momentum_report.py --years 3 --folds 12 --train-bars 2400 --test-bars 300 --purge-bars 12 --out hurst_mtf_momentum_results.csv --matrix-out hurst_mtf_momentum_pbo_matrix.csv --trades-out hurst_mtf_momentum_trades.csv --json-out hurst_mtf_momentum_report.json --md-out docs/HURST_MTF_MOMENTUM_REPORT_2026_05_04.md`

Strict status: `benchmark_only`

Methodology: fixed 8-perp universe, full 72-candidate grid unless
debug-capped by CLI, 12-fold train/test walk-forward, default 12-bar
purge gap before each test window, direction-specific 1h trigger volume
confirmation, severe cost stress, PBO matrix, concentration, tail-capture,
and crisis-alpha checks.

## Strict Gates

| gate | pass |
| --- | --- |
| net_cagr_after_severe_cost_pct | False |
| pbo_below_0_30 | True |
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
| -95.3959 | -84.6355 | 98.7345 | -1.5344 | -1.3754 | 230.204 |

## Concentration / Tail

| positive_folds | sample_trades | symbol_pnl_share | month_pnl_share | tail_capture | failed_checks |
| --- | --- | --- | --- | --- | --- |
| 2 | 454 | 0.0049 | 0.0858 | 0.4323 | net_cagr_after_severe_cost_pct,walk_forward_positive_folds_7_of_12,dsr_proxy_non_negative,sortino_at_least_2,tail_capture_50_to_80_pct,crisis_alpha_positive |

## Selected Candidates

| period | candidate | train_score | train_trades | train_return_pct | purge_bars | embargo_bars | test_start | test_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 5.571358 | 190 | 66.727494 | 12 | 0 | 2024-06-10T20:00:00+00:00 | 2024-07-30T16:00:00+00:00 |
| 2 | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 3.990098 | 235 | 35.656054 | 12 | 0 | 2024-07-30T20:00:00+00:00 | 2024-09-18T16:00:00+00:00 |
| 3 | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 9.586227 | 292 | 149.560522 | 12 | 0 | 2024-09-18T20:00:00+00:00 | 2024-11-07T16:00:00+00:00 |
| 4 | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 6.658704 | 206 | 62.853907 | 12 | 0 | 2024-11-07T20:00:00+00:00 | 2024-12-27T16:00:00+00:00 |
| 5 | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 5.604783 | 261 | 49.869008 | 12 | 0 | 2024-12-27T20:00:00+00:00 | 2025-02-15T16:00:00+00:00 |
| 6 | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 2.21928 | 278 | -0.798251 | 12 | 0 | 2025-02-15T20:00:00+00:00 | 2025-04-06T16:00:00+00:00 |
| 7 | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | -0.866641 | 256 | -34.415549 | 12 | 0 | 2025-04-06T20:00:00+00:00 | 2025-05-26T16:00:00+00:00 |
| 8 | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | -3.302276 | 230 | -55.329799 | 12 | 0 | 2025-05-26T20:00:00+00:00 | 2025-07-15T16:00:00+00:00 |
| 9 | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | -1.273391 | 288 | -41.00858 | 12 | 0 | 2025-07-15T20:00:00+00:00 | 2025-09-03T16:00:00+00:00 |
| 10 | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | -0.816736 | 255 | -35.948931 | 12 | 0 | 2025-09-03T20:00:00+00:00 | 2025-10-23T16:00:00+00:00 |
| 11 | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.60 | -6.492743 | 238 | -79.213689 | 12 | 0 | 2025-10-23T20:00:00+00:00 | 2025-12-12T16:00:00+00:00 |
| 12 | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.60 | -5.939798 | 218 | -76.675617 | 12 | 0 | 2025-12-12T20:00:00+00:00 | 2026-01-31T16:00:00+00:00 |

## Scenario Folds

| period | scenario | candidate | trades | total_return_pct | max_dd_pct | sortino | profit_factor |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | baseline | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 44 | -6.218239 | 35.216185 | 0.116968 | 0.922421 |
| 1 | slippage_30bps | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 44 | -11.884237 | 35.709544 | -0.389975 | 0.853203 |
| 1 | slippage_60bps | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 44 | -22.254647 | 36.944214 | -1.360558 | 0.729746 |
| 1 | funding_2x | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 44 | -7.707153 | 35.284986 | -0.015277 | 0.90419 |
| 1 | severe | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 44 | -23.504666 | 37.190972 | -1.486015 | 0.71536 |
| 2 | baseline | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 56 | 85.08786 | 49.250091 | 4.770893 | 1.501663 |
| 2 | slippage_30bps | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 56 | 73.897531 | 50.508128 | 4.431603 | 1.434189 |
| 2 | slippage_60bps | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 56 | 53.397042 | 52.951728 | 3.751874 | 1.31185 |
| 2 | funding_2x | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 56 | 82.502108 | 49.538253 | 4.694771 | 1.484862 |
| 2 | severe | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 56 | 51.222794 | 53.270065 | 3.675397 | 1.298362 |
| 3 | baseline | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 74 | -56.06664 | 59.669024 | -6.693753 | 0.494801 |
| 3 | slippage_30bps | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 74 | -61.046641 | 63.771958 | -7.630539 | 0.442954 |
| 3 | slippage_60bps | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 74 | -69.429463 | 71.302526 | -9.400393 | 0.352452 |
| 3 | funding_2x | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 74 | -57.55063 | 60.880265 | -6.964626 | 0.478879 |
| 3 | severe | H0.53\|HX0.45\|ADX25\|VZ1.2\|TV0.60 | 74 | -70.481846 | 72.290767 | -9.649061 | 0.340202 |
| 4 | baseline | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 51 | 12.287866 | 29.746684 | 1.31225 | 1.160173 |
| 4 | slippage_30bps | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 51 | 7.940325 | 30.401428 | 1.027199 | 1.103114 |
| 4 | slippage_60bps | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 51 | -0.288848 | 32.518408 | 0.474915 | 0.996271 |
| 4 | funding_2x | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 51 | 11.108394 | 29.928347 | 1.236636 | 1.144487 |
| 4 | severe | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 51 | -1.347431 | 32.812271 | 0.402143 | 0.982632 |
| 5 | baseline | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 38 | -28.508063 | 37.158038 | -2.587549 | 0.488852 |
| 5 | slippage_30bps | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 38 | -30.33448 | 38.335056 | -2.761418 | 0.462761 |
| 5 | slippage_60bps | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 38 | -33.858249 | 40.658002 | -3.091483 | 0.414687 |
| 5 | funding_2x | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 38 | -28.876203 | 37.346588 | -2.624681 | 0.48347 |
| 5 | severe | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 38 | -34.201351 | 40.896702 | -3.125433 | 0.410158 |
| 6 | baseline | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 9 | -10.189224 | 11.47985 | -3.04545 | 0.227335 |
| 6 | slippage_30bps | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 9 | -10.714294 | 11.808733 | -3.195318 | 0.208082 |
| 6 | slippage_60bps | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 9 | -11.75643 | 12.588608 | -3.481868 | 0.179913 |
| 6 | funding_2x | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 9 | -10.336294 | 11.569505 | -3.090051 | 0.221975 |
| 6 | severe | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 9 | -11.901283 | 12.696583 | -3.522283 | 0.176473 |
| 7 | baseline | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 23 | -36.049766 | 42.172249 | -3.836045 | 0.246 |
| 7 | slippage_30bps | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 23 | -37.624769 | 43.231934 | -4.047651 | 0.22901 |
| 7 | slippage_60bps | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 23 | -40.670938 | 45.302422 | -4.438484 | 0.197859 |
| 7 | funding_2x | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 23 | -36.501365 | 42.504477 | -3.887905 | 0.241887 |
| 7 | severe | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 23 | -41.094027 | 45.620058 | -4.486808 | 0.194507 |
| 8 | baseline | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 49 | -7.140698 | 25.038923 | -0.352325 | 0.878325 |
| 8 | slippage_30bps | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 49 | -12.166312 | 25.876003 | -0.874641 | 0.797327 |
| 8 | slippage_60bps | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 49 | -21.463184 | 28.05029 | -1.870941 | 0.655905 |
| 8 | funding_2x | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 49 | -8.305203 | 25.213078 | -0.474791 | 0.859165 |
| 8 | severe | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 49 | -22.460954 | 28.674807 | -1.98463 | 0.641141 |
| 9 | baseline | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 39 | -9.071742 | 26.830845 | -0.732775 | 0.837515 |
| 9 | slippage_30bps | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 39 | -12.462467 | 28.688868 | -1.142829 | 0.779599 |
| 9 | slippage_60bps | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 39 | -18.893799 | 32.276483 | -1.938928 | 0.674575 |
| 9 | funding_2x | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 39 | -9.987566 | 27.418436 | -0.840054 | 0.821737 |
| 9 | severe | H0.58\|HX0.45\|ADX25\|VZ1.5\|TV0.45 | 39 | -19.718623 | 32.824673 | -2.037081 | 0.661716 |
| 10 | baseline | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 18 | -4.600618 | 17.406355 | -0.431585 | 0.846821 |
| 10 | slippage_30bps | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 18 | -6.22226 | 18.353625 | -0.649332 | 0.797211 |
| 10 | slippage_60bps | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 18 | -9.388873 | 20.21962 | -1.075071 | 0.706084 |
| 10 | funding_2x | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 18 | -5.009422 | 17.62889 | -0.486761 | 0.83414 |
| 10 | severe | H0.58\|HX0.45\|ADX25\|VZ2.0\|TV0.45 | 18 | -9.778688 | 20.435643 | -1.128319 | 0.695407 |
| 11 | baseline | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.60 | 24 | -26.097573 | 31.207142 | -3.00397 | 0.321042 |
| 11 | slippage_30bps | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.60 | 24 | -28.486038 | 33.265823 | -3.264116 | 0.285837 |
| 11 | slippage_60bps | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.60 | 24 | -33.049695 | 37.213573 | -3.749571 | 0.227685 |
| 11 | funding_2x | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.60 | 24 | -26.671823 | 31.650948 | -3.081765 | 0.311765 |
| 11 | severe | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.60 | 24 | -33.574074 | 37.621827 | -3.820483 | 0.221063 |
| 12 | baseline | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.60 | 29 | 25.185767 | 35.193364 | 2.165488 | 2.030758 |
| 12 | slippage_30bps | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.60 | 29 | 19.412475 | 36.516917 | 1.760411 | 1.850564 |
| 12 | slippage_60bps | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.60 | 29 | 8.550083 | 39.624318 | 1.010177 | 1.537932 |
| 12 | funding_2x | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.60 | 29 | 23.766821 | 35.486783 | 2.066343 | 1.988249 |
| 12 | severe | H0.58\|HX0.43\|ADX25\|VZ2.0\|TV0.60 | 29 | 7.291473 | 40.162278 | 0.924636 | 1.506317 |

## Decision

Phase B is allowed only if every strict gate is true. If status is
`benchmark_only`, this candidate stays research-only and should be reviewed
before any further engineering work.
