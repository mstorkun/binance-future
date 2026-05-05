# Range Mean-Reversion Report - 2026-05-05

Status: research-only. This does not enable paper, testnet, or live execution.

Command: `range_reversion_report.py --years 3 --folds 12 --train-bars 7200 --test-bars 900 --purge-bars 24 --out range_reversion_results.csv --matrix-out range_reversion_pbo_matrix.csv --trades-out range_reversion_trades.csv --json-out range_reversion_report.json --md-out docs/RANGE_REVERSION_REPORT_2026_05_05.md`

Strict status: `benchmark_only`

Methodology: fixed 8-perp universe, 1h entries from prior closed 1h bars,
4h low-ADX regime filter, optional reclaim mode, daily trend opposition guard,
12-fold train/test walk-forward, purge gap, severe cost stress, PBO matrix,
concentration, tail-capture, and crisis-alpha checks. This is a separate
mean-reversion family and is not connected to paper/live order behavior.

## Strict Gates

| gate | pass |
| --- | --- |
| net_cagr_after_severe_cost_pct | False |
| pbo_below_0_30 | True |
| walk_forward_positive_folds_7_of_12 | False |
| dsr_proxy_non_negative | False |
| sortino_at_least_2 | False |
| no_symbol_over_40_pct_pnl | False |
| no_month_over_25_pct_pnl | True |
| tail_capture_50_to_80_pct | False |
| crisis_alpha_positive | False |
| sample_at_least_200_trades | False |

## Severe Metrics

| total_return_pct | cagr_pct | max_dd_pct | sortino | sharpe | final_equity |
| --- | --- | --- | --- | --- | --- |
| -51.8707 | -44.7446 | 52.1327 | -1.4618 | -6.1892 | 2406.4647 |

## Concentration / Tail

| positive_folds | sample_trades | symbol_pnl_share | month_pnl_share | tail_capture | failed_checks |
| --- | --- | --- | --- | --- | --- |
| 1 | 136 | 1.0 | 0.0156 | 0.281 | net_cagr_after_severe_cost_pct,walk_forward_positive_folds_7_of_12,dsr_proxy_non_negative,sortino_at_least_2,no_symbol_over_40_pct_pnl,tail_capture_50_to_80_pct,crisis_alpha_positive,sample_at_least_200_trades |

## Selected Candidates

| period | candidate | train_score | train_trades | train_return_pct | purge_bars | embargo_bars | test_start | test_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | LB48\|Z1.5\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | -2.73294 | 128 | -13.040295 | 24 | 0 | 2024-02-21T10:00:00+00:00 | 2024-03-29T21:00:00+00:00 |
| 2 | LB48\|Z1.5\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | -2.380765 | 110 | -12.078285 | 24 | 0 | 2024-03-29T22:00:00+00:00 | 2024-05-06T09:00:00+00:00 |
| 3 | LB24\|Z1.2\|RSI35-65\|BADX30\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | -3.208859 | 108 | -22.00268 | 24 | 0 | 2024-05-06T10:00:00+00:00 | 2024-06-12T21:00:00+00:00 |
| 4 | LB24\|Z1.2\|RSI35-65\|BADX30\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | -2.957497 | 97 | -17.759473 | 24 | 0 | 2024-06-12T22:00:00+00:00 | 2024-07-20T09:00:00+00:00 |
| 5 | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | -2.660832 | 61 | -12.420163 | 24 | 0 | 2024-07-20T10:00:00+00:00 | 2024-08-26T21:00:00+00:00 |
| 6 | LB24\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | -2.186222 | 61 | -7.082961 | 24 | 0 | 2024-08-26T22:00:00+00:00 | 2024-10-03T09:00:00+00:00 |
| 7 | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | -1.087977 | 60 | -2.789532 | 24 | 0 | 2024-10-03T10:00:00+00:00 | 2024-11-09T21:00:00+00:00 |
| 8 | LB72\|Z1.2\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | -2.79327 | 65 | -8.429842 | 24 | 0 | 2024-11-09T22:00:00+00:00 | 2024-12-17T09:00:00+00:00 |
| 9 | LB72\|Z1.2\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | -2.297232 | 65 | -6.767387 | 24 | 0 | 2024-12-17T10:00:00+00:00 | 2025-01-23T21:00:00+00:00 |
| 10 | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | -1.993088 | 68 | -5.288703 | 24 | 0 | 2025-01-23T22:00:00+00:00 | 2025-03-02T09:00:00+00:00 |
| 11 | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | -2.583315 | 71 | -7.181257 | 24 | 0 | 2025-03-02T10:00:00+00:00 | 2025-04-08T21:00:00+00:00 |
| 12 | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | -3.443531 | 76 | -14.986925 | 24 | 0 | 2025-04-08T22:00:00+00:00 | 2025-05-16T09:00:00+00:00 |

## Scenario Folds

| period | scenario | candidate | trades | total_return_pct | max_dd_pct | sortino | profit_factor |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | baseline | LB48\|Z1.5\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 10 | -3.87779 | 4.841209 | -0.903034 | 0.353694 |
| 1 | slippage_30bps | LB48\|Z1.5\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 10 | -4.492961 | 5.332073 | -0.98748 | 0.296838 |
| 1 | slippage_60bps | LB48\|Z1.5\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 10 | -5.712973 | 6.30744 | -1.139035 | 0.20242 |
| 1 | funding_2x | LB48\|Z1.5\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 10 | -3.895241 | 4.855376 | -0.906867 | 0.352124 |
| 1 | severe | LB48\|Z1.5\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 10 | -5.73014 | 6.321433 | -1.142046 | 0.201384 |
| 2 | baseline | LB48\|Z1.5\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 14 | -6.963359 | 7.605711 | -2.626919 | 0.158625 |
| 2 | slippage_30bps | LB48\|Z1.5\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 14 | -7.75429 | 8.35874 | -2.790894 | 0.129476 |
| 2 | slippage_60bps | LB48\|Z1.5\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 14 | -9.317652 | 9.847935 | -3.06488 | 0.082732 |
| 2 | funding_2x | LB48\|Z1.5\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 14 | -6.988468 | 7.629001 | -2.632037 | 0.157438 |
| 2 | severe | LB48\|Z1.5\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 14 | -9.342166 | 9.870696 | -3.068462 | 0.081925 |
| 3 | baseline | LB24\|Z1.2\|RSI35-65\|BADX30\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 15 | -7.331148 | 9.541986 | -1.663761 | 0.307927 |
| 3 | slippage_30bps | LB24\|Z1.2\|RSI35-65\|BADX30\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 15 | -8.951089 | 10.669804 | -1.92592 | 0.213645 |
| 3 | slippage_60bps | LB24\|Z1.2\|RSI35-65\|BADX30\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 15 | -12.113935 | 12.888688 | -2.399895 | 0.073421 |
| 3 | funding_2x | LB24\|Z1.2\|RSI35-65\|BADX30\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 15 | -7.397264 | 9.583739 | -1.671304 | 0.30369 |
| 3 | severe | LB24\|Z1.2\|RSI35-65\|BADX30\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 15 | -12.17696 | 12.929138 | -2.404328 | 0.072245 |
| 4 | baseline | LB24\|Z1.2\|RSI35-65\|BADX30\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 12 | -7.55033 | 8.933303 | -2.139429 | 0.22 |
| 4 | slippage_30bps | LB24\|Z1.2\|RSI35-65\|BADX30\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 12 | -8.828988 | 10.040521 | -2.249503 | 0.157503 |
| 4 | slippage_60bps | LB24\|Z1.2\|RSI35-65\|BADX30\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 12 | -11.338749 | 12.21918 | -2.457953 | 0.063957 |
| 4 | funding_2x | LB24\|Z1.2\|RSI35-65\|BADX30\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 12 | -7.575904 | 8.955924 | -2.146585 | 0.218475 |
| 4 | severe | LB24\|Z1.2\|RSI35-65\|BADX30\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 12 | -11.363382 | 12.241075 | -2.462086 | 0.063246 |
| 5 | baseline | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 12 | -0.555628 | 2.734717 | -0.136254 | 0.865906 |
| 5 | slippage_30bps | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 12 | -1.616151 | 3.391122 | -0.383985 | 0.639187 |
| 5 | slippage_60bps | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 12 | -3.706432 | 4.764126 | -0.808695 | 0.279236 |
| 5 | funding_2x | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 12 | -0.58836 | 2.757864 | -0.144258 | 0.858403 |
| 5 | severe | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 12 | -3.738227 | 4.78771 | -0.81361 | 0.274762 |
| 6 | baseline | LB24\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 20 | -4.009229 | 6.326324 | -1.104064 | 0.528098 |
| 6 | slippage_30bps | LB24\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 20 | -5.58128 | 7.179484 | -1.503714 | 0.388303 |
| 6 | slippage_60bps | LB24\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 20 | -8.654014 | 9.251705 | -2.227027 | 0.165034 |
| 6 | funding_2x | LB24\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 20 | -4.068803 | 6.354985 | -1.117255 | 0.522391 |
| 6 | severe | LB24\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 20 | -8.710978 | 9.304663 | -2.237267 | 0.161731 |
| 7 | baseline | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 8 | -3.581204 | 3.954044 | -1.277825 | 0.248297 |
| 7 | slippage_30bps | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 8 | -4.244753 | 4.538704 | -1.427272 | 0.183068 |
| 7 | slippage_60bps | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 8 | -5.560095 | 5.699098 | -1.677239 | 0.081653 |
| 7 | funding_2x | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 8 | -3.612914 | 3.984992 | -1.287247 | 0.245394 |
| 7 | severe | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 8 | -5.591254 | 5.72958 | -1.684562 | 0.080068 |
| 8 | baseline | LB72\|Z1.2\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 4 | 1.724651 | 0.474425 | 0.902219 | 86.2325 |
| 8 | slippage_30bps | LB72\|Z1.2\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 4 | 1.499073 | 0.474604 | 0.787536 | 74.9537 |
| 8 | slippage_60bps | LB72\|Z1.2\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 4 | 1.048956 | 0.484313 | 0.619204 | 52.4478 |
| 8 | funding_2x | LB72\|Z1.2\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 4 | 1.717198 | 0.474425 | 0.89836 | 85.8599 |
| 8 | severe | LB72\|Z1.2\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 4 | 1.041542 | 0.484313 | 0.616632 | 52.077 |
| 9 | baseline | LB72\|Z1.2\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 15 | -1.286996 | 2.722773 | -0.409088 | 0.712435 |
| 9 | slippage_30bps | LB72\|Z1.2\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 15 | -2.176682 | 3.041677 | -0.683152 | 0.550886 |
| 9 | slippage_60bps | LB72\|Z1.2\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 15 | -3.934928 | 4.739573 | -1.178199 | 0.296244 |
| 9 | funding_2x | LB72\|Z1.2\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 15 | -1.321194 | 2.73802 | -0.418254 | 0.706269 |
| 9 | severe | LB72\|Z1.2\|RSI35-65\|BADX30\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 15 | -3.96833 | 4.769288 | -1.182924 | 0.293144 |
| 10 | baseline | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 10 | -3.104403 | 3.485622 | -1.292732 | 0.332146 |
| 10 | slippage_30bps | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 10 | -3.77786 | 4.048575 | -1.456821 | 0.255285 |
| 10 | slippage_60bps | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 10 | -5.112435 | 5.165955 | -1.694326 | 0.135855 |
| 10 | funding_2x | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 10 | -3.13769 | 3.512452 | -1.303998 | 0.328263 |
| 10 | severe | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 10 | -5.145122 | 5.192387 | -1.701276 | 0.133604 |
| 11 | baseline | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 13 | -2.655704 | 3.405193 | -0.868665 | 0.428479 |
| 11 | slippage_30bps | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 13 | -3.379088 | 4.012806 | -1.08305 | 0.334624 |
| 11 | slippage_60bps | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 13 | -4.811062 | 5.217692 | -1.458011 | 0.189358 |
| 11 | funding_2x | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 13 | -2.665418 | 3.41257 | -0.871749 | 0.426978 |
| 11 | severe | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.35\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 13 | -4.820579 | 5.224944 | -1.460619 | 0.188397 |
| 12 | baseline | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 3 | 0.24601 | 0.899169 | 0.131248 | 1.270471 |
| 12 | slippage_30bps | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 3 | 0.014178 | 0.975192 | 0.009642 | 1.014393 |
| 12 | slippage_60bps | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 3 | -0.448593 | 1.146577 | -0.200245 | 0.604755 |
| 12 | funding_2x | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 3 | 0.236912 | 0.901704 | 0.126003 | 1.259754 |
| 12 | severe | LB72\|Z1.2\|RSI35-65\|BADX26\|TV0.50\|SL1.5\|TP1.0\|BW0.006\|REC1\|AVD1 | 3 | -0.457663 | 1.154334 | -0.204236 | 0.597641 |

## Decision

If status is `benchmark_only`, this candidate stays research-only and
must not be connected to paper or live execution.
