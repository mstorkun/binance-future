# Hurst MTF Trade Diagnostics - 2026-05-05

Status: diagnostic-only. This does not enable paper, testnet, or live execution.

## Primary Findings

- Hard-stop losses are the main structural leak.
- Trailing-stop winners are strong enough to preserve; the issue is failed-entry control, not absence of winners.
- Immediate reentries after losing hard_stop/time_stop/regime_exit are negative and should be tested as a cooldown variant.
- Baseline is also negative, so the result is not only caused by severe cost stress.
- Live market validation remains mandatory, but only after paper/shadow and micro-live gates are explicit.

## Key Numbers

| hard_stop_trades | hard_stop_pnl | trailing_stop_trades | trailing_stop_pnl | baseline_compound_return_pct | severe_compound_return_pct | losing_exit_reentry_trades | losing_exit_reentry_pnl | winning_trailing_reentry_trades | winning_trailing_reentry_pnl | selected_next_candidate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 124 | -27898.185 | 132 | 25565.9561 | -73.798 | -95.3959 | 109 | -8038.1325 | 91 | 3678.0203 | HURST_MTF_COOLDOWN_V2 |

## Scenario Compounds

| scenario | folds | positive_folds | compound_return_pct | worst_fold_pct | best_fold_pct |
| --- | --- | --- | --- | --- | --- |
| baseline | 12 | 3 | -73.798 | -56.0666 | 85.0879 |
| slippage_30bps | 12 | 3 | -84.6084 | -61.0466 | 73.8975 |
| slippage_60bps | 12 | 2 | -94.7197 | -69.4295 | 53.397 |
| funding_2x | 12 | 3 | -77.1096 | -57.5506 | 82.5021 |
| severe | 12 | 2 | -95.3959 | -70.4818 | 51.2228 |

## Exit Reason

| exit_reason | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| hard_stop | 124 | -27898.185 | -224.9854 | 0.0 | 0.0 |
| time_stop | 145 | -6567.7901 | -45.2951 | 0.3379 | 0.3074 |
| regime_exit | 44 | -1601.5397 | -36.3986 | 0.3864 | 0.488 |
| end_of_sample | 9 | 983.9539 | 109.3282 | 0.6667 | 11.5612 |
| trailing_stop | 132 | 25565.9561 | 193.6815 | 1.0 | 25565.9561 |

## Side

| side | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| long | 234 | -8431.3862 | -36.0316 | 0.4316 | 0.5578 |
| short | 220 | -1086.2186 | -4.9374 | 0.4682 | 0.9496 |

## Reentry Diagnostics

| gap_hours_lte | trades | pnl | avg_pnl | win_rate |
| --- | --- | --- | --- | --- |
| 0.0 | 150 | -1928.7384 | -12.8583 | 0.4467 |
| 4.0 | 180 | -2871.0161 | -15.9501 | 0.4444 |
| 8.0 | 189 | -2986.5576 | -15.8019 | 0.4444 |
| 12.0 | 202 | -4093.7952 | -20.2663 | 0.4455 |
| 24.0 | 226 | -5331.1239 | -23.589 | 0.4381 |

## After Losing Exit Reentries

| prev_reason | side | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- | --- |
| hard_stop | long | 38 | -4374.3292 | -115.1139 | 0.1316 | 0.1589 |
| hard_stop | short | 36 | -3093.9827 | -85.944 | 0.3056 | 0.2396 |
| time_stop | short | 15 | -698.743 | -46.5829 | 0.4 | 0.3619 |
| time_stop | long | 16 | -185.6203 | -11.6013 | 0.5625 | 0.7951 |
| regime_exit | short | 1 | 121.0225 | 121.0225 | 1.0 | 121.0225 |
| regime_exit | long | 3 | 193.5202 | 64.5067 | 1.0 | 193.5202 |

## After Winning Trailing Reentries

| side | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| long | 43 | 596.8455 | 13.8801 | 0.6279 | 1.2261 |
| short | 48 | 3081.1748 | 64.1911 | 0.5625 | 1.4441 |

## Worst Symbols

| symbol | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| AVAX/USDT:USDT | 70 | -3302.859 | -47.1837 | 0.4 | 0.5824 |
| BTC/USDT:USDT | 63 | -2089.8961 | -33.173 | 0.5079 | 0.6149 |
| BNB/USDT:USDT | 26 | -1251.846 | -48.1479 | 0.4231 | 0.5333 |
| SOL/USDT:USDT | 46 | -1154.3266 | -25.0941 | 0.4565 | 0.6252 |
| XRP/USDT:USDT | 49 | -1148.5038 | -23.4389 | 0.449 | 0.707 |
| DOGE/USDT:USDT | 68 | -445.3115 | -6.5487 | 0.4559 | 0.9151 |
| LINK/USDT:USDT | 65 | -276.0239 | -4.2465 | 0.4615 | 0.9555 |
| ETH/USDT:USDT | 67 | 151.1621 | 2.2562 | 0.4328 | 1.0246 |

## Worst Periods

| period | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| 3 | 74 | -3521.7945 | -47.5918 | 0.3378 | 0.3402 |
| 7 | 23 | -2054.7013 | -89.3348 | 0.2174 | 0.1945 |
| 5 | 38 | -1733.1223 | -45.6085 | 0.3421 | 0.4102 |
| 11 | 24 | -1678.7035 | -69.946 | 0.2917 | 0.2211 |
| 1 | 44 | -1175.2334 | -26.7098 | 0.5227 | 0.7154 |
| 8 | 49 | -1123.0475 | -22.9193 | 0.551 | 0.6411 |
| 9 | 39 | -985.931 | -25.2803 | 0.4615 | 0.6617 |
| 6 | 9 | -595.064 | -66.1182 | 0.2222 | 0.1765 |
| 10 | 18 | -488.9346 | -27.163 | 0.4444 | 0.6954 |
| 4 | 51 | -67.3716 | -1.321 | 0.549 | 0.9826 |
| 12 | 29 | 1345.1594 | 46.3848 | 0.6207 | 1.5063 |
| 2 | 56 | 2561.1395 | 45.7346 | 0.5357 | 1.2984 |

## Top Winners

| period | symbol | side | entry_time | exit_time | exit_reason | pnl | bars_held | reached_1r |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | LINK/USDT:USDT | short | 2024-08-05T00:00:00+00:00 | 2024-08-05T04:00:00+00:00 | trailing_stop | 1774.5419 | 1 | True |
| 2 | ETH/USDT:USDT | short | 2024-08-04T16:00:00+00:00 | 2024-08-05T00:00:00+00:00 | trailing_stop | 1493.307 | 2 | True |
| 2 | ETH/USDT:USDT | short | 2024-08-05T00:00:00+00:00 | 2024-08-05T04:00:00+00:00 | trailing_stop | 1303.4046 | 1 | True |
| 2 | DOGE/USDT:USDT | short | 2024-08-05T00:00:00+00:00 | 2024-08-05T04:00:00+00:00 | trailing_stop | 1035.0392 | 1 | True |
| 2 | AVAX/USDT:USDT | short | 2024-08-05T00:00:00+00:00 | 2024-08-05T04:00:00+00:00 | trailing_stop | 754.0617 | 1 | True |
| 12 | ETH/USDT:USDT | short | 2026-01-31T12:00:00+00:00 | 2026-01-31T16:00:00+00:00 | trailing_stop | 650.3862 | 1 | True |
| 2 | LINK/USDT:USDT | short | 2024-08-04T16:00:00+00:00 | 2024-08-05T00:00:00+00:00 | trailing_stop | 640.3876 | 2 | True |
| 1 | XRP/USDT:USDT | short | 2024-07-04T20:00:00+00:00 | 2024-07-05T00:00:00+00:00 | trailing_stop | 541.1223 | 1 | True |
| 2 | AVAX/USDT:USDT | short | 2024-08-04T16:00:00+00:00 | 2024-08-05T00:00:00+00:00 | trailing_stop | 471.801 | 2 | True |
| 10 | BNB/USDT:USDT | long | 2025-10-11T00:00:00+00:00 | 2025-10-13T08:00:00+00:00 | trailing_stop | 453.849 | 14 | True |

## Top Losers

| period | symbol | side | entry_time | exit_time | exit_reason | pnl | bars_held | reached_1r |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | LINK/USDT:USDT | short | 2024-08-05T12:00:00+00:00 | 2024-08-06T00:00:00+00:00 | hard_stop | -1301.5986 | 3 | False |
| 2 | AVAX/USDT:USDT | short | 2024-08-05T04:00:00+00:00 | 2024-08-06T04:00:00+00:00 | hard_stop | -1069.2385 | 6 | False |
| 2 | ETH/USDT:USDT | short | 2024-08-05T04:00:00+00:00 | 2024-08-07T04:00:00+00:00 | time_stop | -1007.5703 | 12 | False |
| 2 | LINK/USDT:USDT | short | 2024-08-06T00:00:00+00:00 | 2024-08-06T16:00:00+00:00 | regime_exit | -601.2685 | 4 | False |
| 2 | XRP/USDT:USDT | short | 2024-08-07T04:00:00+00:00 | 2024-08-07T20:00:00+00:00 | hard_stop | -585.044 | 4 | False |
| 2 | DOGE/USDT:USDT | short | 2024-08-05T04:00:00+00:00 | 2024-08-06T12:00:00+00:00 | regime_exit | -497.6197 | 8 | False |
| 3 | DOGE/USDT:USDT | long | 2024-09-30T04:00:00+00:00 | 2024-09-30T20:00:00+00:00 | hard_stop | -372.9964 | 4 | False |
| 1 | DOGE/USDT:USDT | short | 2024-07-05T08:00:00+00:00 | 2024-07-06T00:00:00+00:00 | hard_stop | -371.004 | 4 | False |
| 1 | XRP/USDT:USDT | short | 2024-07-05T12:00:00+00:00 | 2024-07-06T16:00:00+00:00 | hard_stop | -369.1083 | 7 | False |
| 4 | ETH/USDT:USDT | long | 2024-11-12T04:00:00+00:00 | 2024-11-13T04:00:00+00:00 | hard_stop | -368.5056 | 6 | False |

## Next Candidate

| name | scope | live_validation |
| --- | --- | --- |
| HURST_MTF_COOLDOWN_V2 | Add 24h same-symbol cooldown only after losing hard_stop/time_stop/regime_exit; keep trailing winners unrestricted; rerun full strict gate. | If a future variant passes strict research gates, run live-market shadow/paper first, then micro-live with hard daily loss and kill-switch limits before scaling. |
