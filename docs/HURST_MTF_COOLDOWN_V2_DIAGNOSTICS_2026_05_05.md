# Hurst MTF Trade Diagnostics - 2026-05-05

Status: diagnostic-only. This does not enable paper, testnet, or live execution.

## Primary Findings

- Hard-stop losses are the main structural leak.
- Trailing-stop winners are strong enough to preserve; the issue is repeated failed entries and whipsaw, not absence of winners.
- Immediate reentries after losing hard_stop/time_stop/regime_exit are negative and should be tested as a cooldown variant.
- Baseline is also negative, so the result is not only caused by severe cost stress.
- Live market validation remains mandatory, but only after paper/shadow and micro-live gates are explicit.

## Key Numbers

| hard_stop_trades | hard_stop_pnl | trailing_stop_trades | trailing_stop_pnl | baseline_compound_return_pct | severe_compound_return_pct | losing_exit_reentry_trades | losing_exit_reentry_pnl | winning_trailing_reentry_trades | winning_trailing_reentry_pnl | selected_next_candidate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 92 | -23829.228 | 122 | 26549.7393 | 20.5578 | -70.5401 | 20 | -449.9821 | 84 | 4634.1714 | HURST_MTF_COST_ROBUST_V3 |

## Scenario Compounds

| scenario | folds | positive_folds | compound_return_pct | worst_fold_pct | best_fold_pct |
| --- | --- | --- | --- | --- | --- |
| baseline | 12 | 5 | 20.5578 | -38.4954 | 102.0178 |
| slippage_30bps | 12 | 5 | -21.8637 | -43.2314 | 91.227 |
| slippage_60bps | 12 | 4 | -67.0203 | -51.9297 | 73.6647 |
| funding_2x | 12 | 5 | 7.7497 | -39.9338 | 99.4456 |
| severe | 12 | 4 | -70.5401 | -53.0367 | 71.4357 |

## Exit Reason

| exit_reason | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| hard_stop | 92 | -23829.228 | -259.0133 | 0.0 | 0.0 |
| time_stop | 126 | -5584.1332 | -44.3185 | 0.381 | 0.3286 |
| regime_exit | 31 | -371.2965 | -11.9773 | 0.3871 | 0.7838 |
| end_of_sample | 10 | 437.0407 | 43.7041 | 0.5 | 2.8079 |
| trailing_stop | 122 | 26549.7393 | 217.6208 | 1.0 | 26549.7393 |

## Side

| side | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| long | 177 | -5711.4915 | -32.2683 | 0.4463 | 0.6463 |
| short | 204 | 2913.6138 | 14.2824 | 0.5294 | 1.1622 |

## Reentry Diagnostics

| gap_hours_lte | trades | pnl | avg_pnl | win_rate |
| --- | --- | --- | --- | --- |
| 0.0 | 61 | 5844.5057 | 95.8116 | 0.6721 |
| 4.0 | 79 | 5798.5465 | 73.3993 | 0.6456 |
| 8.0 | 85 | 5561.2852 | 65.4269 | 0.6235 |
| 12.0 | 88 | 4825.7036 | 54.8375 | 0.6136 |
| 24.0 | 122 | 4047.7537 | 33.1783 | 0.5574 |

## After Losing Exit Reentries

| prev_reason | side | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- | --- |
| hard_stop | long | 5 | -808.395 | -161.679 | 0.0 | 0.0 |
| time_stop | short | 5 | -362.116 | -72.4232 | 0.2 | 0.3199 |
| hard_stop | short | 7 | 82.109 | 11.7299 | 0.5714 | 1.2931 |
| time_stop | long | 3 | 638.4199 | 212.8066 | 1.0 | 638.4199 |

## After Winning Trailing Reentries

| side | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| long | 37 | 634.962 | 17.1611 | 0.6216 | 1.2015 |
| short | 47 | 3999.2094 | 85.0896 | 0.5957 | 1.6226 |

## Worst Symbols

| symbol | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| AVAX/USDT:USDT | 58 | -1693.8669 | -29.2046 | 0.4828 | 0.7421 |
| BTC/USDT:USDT | 49 | -1681.9319 | -34.3251 | 0.4898 | 0.601 |
| XRP/USDT:USDT | 45 | -1157.2511 | -25.7167 | 0.4667 | 0.6925 |
| DOGE/USDT:USDT | 69 | -740.8384 | -10.7368 | 0.4928 | 0.8758 |
| BNB/USDT:USDT | 20 | -471.1292 | -23.5565 | 0.4 | 0.7482 |
| SOL/USDT:USDT | 37 | -48.982 | -1.3238 | 0.5676 | 0.9784 |
| ETH/USDT:USDT | 53 | 1377.1621 | 25.9842 | 0.5094 | 1.283 |
| LINK/USDT:USDT | 50 | 1618.9597 | 32.3792 | 0.48 | 1.353 |

## Worst Periods

| period | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| 3 | 50 | -2672.1734 | -53.4435 | 0.36 | 0.3233 |
| 7 | 18 | -2039.2415 | -113.2912 | 0.2222 | 0.1344 |
| 5 | 28 | -1158.809 | -41.386 | 0.3929 | 0.5963 |
| 1 | 23 | -938.1708 | -40.79 | 0.4783 | 0.5879 |
| 6 | 12 | -841.467 | -70.1222 | 0.25 | 0.2657 |
| 11 | 30 | -757.4579 | -25.2486 | 0.4667 | 0.5047 |
| 9 | 27 | -679.1292 | -25.1529 | 0.4444 | 0.6313 |
| 8 | 41 | -317.4286 | -7.7422 | 0.6098 | 0.869 |
| 10 | 13 | 26.6159 | 2.0474 | 0.4615 | 1.0299 |
| 4 | 45 | 897.3477 | 19.9411 | 0.5778 | 1.2091 |
| 12 | 44 | 2110.2498 | 47.9602 | 0.6591 | 1.8716 |
| 2 | 50 | 3571.7863 | 71.4357 | 0.56 | 1.4403 |

## Top Winners

| period | symbol | side | entry_time | exit_time | exit_reason | pnl | bars_held | reached_1r |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | LINK/USDT:USDT | short | 2024-08-05T00:00:00+00:00 | 2024-08-05T04:00:00+00:00 | trailing_stop | 1871.6951 | 1 | True |
| 2 | ETH/USDT:USDT | short | 2024-08-04T16:00:00+00:00 | 2024-08-05T00:00:00+00:00 | trailing_stop | 1575.0631 | 2 | True |
| 2 | ETH/USDT:USDT | short | 2024-08-05T00:00:00+00:00 | 2024-08-05T04:00:00+00:00 | trailing_stop | 1374.7638 | 1 | True |
| 2 | DOGE/USDT:USDT | short | 2024-08-05T00:00:00+00:00 | 2024-08-05T04:00:00+00:00 | trailing_stop | 1091.7059 | 1 | True |
| 2 | AVAX/USDT:USDT | short | 2024-08-05T00:00:00+00:00 | 2024-08-05T04:00:00+00:00 | trailing_stop | 795.3453 | 1 | True |
| 2 | LINK/USDT:USDT | short | 2024-08-04T16:00:00+00:00 | 2024-08-05T00:00:00+00:00 | trailing_stop | 675.4477 | 2 | True |
| 12 | ETH/USDT:USDT | short | 2026-01-31T12:00:00+00:00 | 2026-01-31T16:00:00+00:00 | trailing_stop | 607.0521 | 1 | True |
| 4 | LINK/USDT:USDT | long | 2024-12-02T16:00:00+00:00 | 2024-12-02T20:00:00+00:00 | trailing_stop | 527.4062 | 1 | True |
| 2 | AVAX/USDT:USDT | short | 2024-08-04T16:00:00+00:00 | 2024-08-05T00:00:00+00:00 | trailing_stop | 497.6313 | 2 | True |
| 5 | AVAX/USDT:USDT | short | 2025-02-02T20:00:00+00:00 | 2025-02-03T00:00:00+00:00 | trailing_stop | 484.0892 | 1 | True |

## Top Losers

| period | symbol | side | entry_time | exit_time | exit_reason | pnl | bars_held | reached_1r |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | LINK/USDT:USDT | short | 2024-08-05T12:00:00+00:00 | 2024-08-06T00:00:00+00:00 | hard_stop | -1372.859 | 3 | False |
| 2 | AVAX/USDT:USDT | short | 2024-08-05T04:00:00+00:00 | 2024-08-06T04:00:00+00:00 | hard_stop | -1127.7776 | 6 | False |
| 2 | ETH/USDT:USDT | short | 2024-08-05T04:00:00+00:00 | 2024-08-07T04:00:00+00:00 | time_stop | -1062.7331 | 12 | False |
| 2 | XRP/USDT:USDT | short | 2024-08-07T04:00:00+00:00 | 2024-08-07T20:00:00+00:00 | hard_stop | -675.5599 | 4 | False |
| 4 | ETH/USDT:USDT | long | 2024-11-12T04:00:00+00:00 | 2024-11-13T04:00:00+00:00 | hard_stop | -534.5834 | 6 | False |
| 2 | DOGE/USDT:USDT | short | 2024-08-05T04:00:00+00:00 | 2024-08-06T12:00:00+00:00 | regime_exit | -524.8635 | 8 | False |
| 4 | AVAX/USDT:USDT | long | 2024-11-12T08:00:00+00:00 | 2024-11-12T12:00:00+00:00 | hard_stop | -498.901 | 1 | False |
| 2 | AVAX/USDT:USDT | short | 2024-09-06T12:00:00+00:00 | 2024-09-08T04:00:00+00:00 | hard_stop | -452.7849 | 10 | False |
| 4 | DOGE/USDT:USDT | long | 2024-11-12T08:00:00+00:00 | 2024-11-12T12:00:00+00:00 | hard_stop | -422.4985 | 1 | False |
| 4 | XRP/USDT:USDT | long | 2024-12-03T00:00:00+00:00 | 2024-12-03T12:00:00+00:00 | hard_stop | -399.6754 | 3 | False |

## Next Candidate

| name | scope | live_validation |
| --- | --- | --- |
| HURST_MTF_COST_ROBUST_V3 | Keep cooldown; reduce turnover and require enough expected move/volatility cushion to survive severe cost stress before any entry. | Use live-market paper/shadow to compare theoretical fills with realistic maker/taker/slippage before any micro-live deployment. |
