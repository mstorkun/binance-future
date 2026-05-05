# Hurst MTF Cost-Robust V3 Diagnostics - 2026-05-05

Status: diagnostic-only. This does not enable paper, testnet, or live execution.

## Primary Findings

- Hard-stop losses are the main structural leak.
- Trailing-stop winners are strong enough to preserve; the issue is failed-entry control, not absence of winners.
- Losing-exit reentry is no longer the dominant leak after cooldown.
- Baseline is positive but severe cost stress is negative, so the remaining issue is cost/turnover fragility.
- This family should not be promoted to micro-live; switch to a different alpha family unless a future independent candidate passes strict research gates.

## Key Numbers

| hard_stop_trades | hard_stop_pnl | trailing_stop_trades | trailing_stop_pnl | baseline_compound_return_pct | severe_compound_return_pct | losing_exit_reentry_trades | losing_exit_reentry_pnl | winning_trailing_reentry_trades | winning_trailing_reentry_pnl | selected_next_candidate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 58 | -17641.6079 | 83 | 22887.4962 | 26.9181 | -45.0242 | 16 | 257.6297 | 66 | 4344.2004 | LEAVE_HURST_MTF_FAMILY |

## Scenario Compounds

| scenario | folds | positive_folds | compound_return_pct | worst_fold_pct | best_fold_pct |
| --- | --- | --- | --- | --- | --- |
| baseline | 12 | 5 | 26.9181 | -30.1662 | 110.8214 |
| slippage_30bps | 12 | 5 | -1.5557 | -32.1275 | 105.9701 |
| slippage_60bps | 12 | 5 | -41.2346 | -40.0974 | 96.5517 |
| funding_2x | 12 | 5 | 18.8118 | -30.4529 | 109.896 |
| severe | 12 | 5 | -45.0242 | -41.2399 | 95.6775 |

## Exit Reason

| exit_reason | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| hard_stop | 58 | -17641.6079 | -304.1657 | 0.0 | 0.0 |
| time_stop | 83 | -4817.193 | -58.0385 | 0.3253 | 0.2688 |
| regime_exit | 12 | -675.0734 | -56.2561 | 0.3333 | 0.3695 |
| end_of_sample | 10 | 386.7249 | 38.6725 | 0.5 | 2.373 |
| trailing_stop | 83 | 22887.4962 | 275.753 | 1.0 | 22887.4962 |

## Side

| side | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| long | 125 | -2983.8416 | -23.8707 | 0.456 | 0.7626 |
| short | 121 | 3124.1884 | 25.8197 | 0.5124 | 1.2401 |

## Reentry Diagnostics

| gap_hours_lte | trades | pnl | avg_pnl | win_rate |
| --- | --- | --- | --- | --- |
| 0.0 | 47 | 4508.7586 | 95.931 | 0.617 |
| 4.0 | 62 | 3809.1716 | 61.4383 | 0.5484 |
| 8.0 | 66 | 4122.5682 | 62.4632 | 0.5455 |
| 12.0 | 69 | 3765.3357 | 54.5701 | 0.5362 |
| 24.0 | 91 | 3671.5938 | 40.3472 | 0.5055 |

## After Losing Exit Reentries

| prev_reason | side | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- | --- |
| hard_stop | long | 5 | -525.564 | -105.1128 | 0.2 | 0.0952 |
| time_stop | short | 4 | -378.3054 | -94.5764 | 0.0 | 0.0 |
| regime_exit | short | 1 | -78.5481 | -78.5481 | 0.0 | 0.0 |
| hard_stop | short | 4 | 480.4968 | 120.1242 | 0.75 | 455.1987 |
| time_stop | long | 2 | 759.5504 | 379.7752 | 1.0 | 759.5504 |

## After Winning Trailing Reentries

| side | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| long | 36 | 913.8363 | 25.3843 | 0.6111 | 1.2742 |
| short | 30 | 3430.3641 | 114.3455 | 0.5333 | 1.5808 |

## Worst Symbols

| symbol | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| XRP/USDT:USDT | 31 | -1530.7913 | -49.3804 | 0.3226 | 0.4921 |
| AVAX/USDT:USDT | 49 | -1261.6745 | -25.7485 | 0.5102 | 0.7848 |
| SOL/USDT:USDT | 25 | -366.7179 | -14.6687 | 0.56 | 0.8404 |
| DOGE/USDT:USDT | 60 | -337.652 | -5.6275 | 0.45 | 0.9442 |
| BTC/USDT:USDT | 7 | 734.7033 | 104.9576 | 0.8571 | 8.5977 |
| BNB/USDT:USDT | 7 | 812.8677 | 116.124 | 0.5714 | 3.2057 |
| LINK/USDT:USDT | 44 | 926.9115 | 21.0662 | 0.5 | 1.1995 |
| ETH/USDT:USDT | 23 | 1162.7 | 50.5522 | 0.4783 | 1.3584 |

## Worst Periods

| period | trades | pnl | avg_pnl | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- |
| 3 | 43 | -2104.9033 | -48.9512 | 0.3953 | 0.4016 |
| 7 | 10 | -1648.922 | -164.8922 | 0.2 | 0.1117 |
| 9 | 33 | -1333.1115 | -40.3973 | 0.3636 | 0.5518 |
| 1 | 13 | -1089.1796 | -83.783 | 0.3846 | 0.3716 |
| 8 | 15 | -910.0362 | -60.6691 | 0.5333 | 0.3012 |
| 6 | 8 | -413.938 | -51.7423 | 0.375 | 0.4468 |
| 11 | 9 | -276.296 | -30.6996 | 0.3333 | 0.3791 |
| 4 | 41 | 8.2658 | 0.2016 | 0.5122 | 1.0018 |
| 5 | 20 | 323.0434 | 16.1522 | 0.55 | 1.164 |
| 10 | 12 | 702.8928 | 58.5744 | 0.5833 | 1.7626 |
| 12 | 19 | 2098.656 | 110.4556 | 0.7368 | 3.6276 |
| 2 | 23 | 4783.8754 | 207.9946 | 0.6957 | 1.9972 |

## Top Winners

| period | symbol | side | entry_time | exit_time | exit_reason | pnl | bars_held | reached_1r |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | LINK/USDT:USDT | short | 2024-08-05T00:00:00+00:00 | 2024-08-05T04:00:00+00:00 | trailing_stop | 1887.2421 | 1 | True |
| 2 | ETH/USDT:USDT | short | 2024-08-04T20:00:00+00:00 | 2024-08-05T00:00:00+00:00 | trailing_stop | 1399.823 | 1 | True |
| 2 | ETH/USDT:USDT | short | 2024-08-05T00:00:00+00:00 | 2024-08-05T04:00:00+00:00 | trailing_stop | 1386.1831 | 1 | True |
| 2 | DOGE/USDT:USDT | short | 2024-08-05T00:00:00+00:00 | 2024-08-05T04:00:00+00:00 | trailing_stop | 1100.774 | 1 | True |
| 2 | AVAX/USDT:USDT | short | 2024-08-05T00:00:00+00:00 | 2024-08-05T04:00:00+00:00 | trailing_stop | 801.9517 | 1 | True |
| 2 | LINK/USDT:USDT | short | 2024-08-04T16:00:00+00:00 | 2024-08-05T00:00:00+00:00 | trailing_stop | 699.0308 | 2 | True |
| 5 | AVAX/USDT:USDT | short | 2025-02-02T20:00:00+00:00 | 2025-02-03T00:00:00+00:00 | trailing_stop | 670.8409 | 1 | True |
| 12 | ETH/USDT:USDT | short | 2026-01-31T12:00:00+00:00 | 2026-01-31T16:00:00+00:00 | trailing_stop | 648.397 | 1 | True |
| 10 | BNB/USDT:USDT | long | 2025-10-11T04:00:00+00:00 | 2025-10-13T08:00:00+00:00 | trailing_stop | 603.4835 | 13 | True |
| 2 | AVAX/USDT:USDT | short | 2024-08-04T16:00:00+00:00 | 2024-08-05T00:00:00+00:00 | trailing_stop | 515.006 | 2 | True |

## Top Losers

| period | symbol | side | entry_time | exit_time | exit_reason | pnl | bars_held | reached_1r |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | LINK/USDT:USDT | short | 2024-08-05T12:00:00+00:00 | 2024-08-06T00:00:00+00:00 | hard_stop | -1384.2625 | 3 | False |
| 2 | AVAX/USDT:USDT | short | 2024-08-05T04:00:00+00:00 | 2024-08-06T04:00:00+00:00 | hard_stop | -1137.1453 | 6 | False |
| 2 | ETH/USDT:USDT | short | 2024-08-05T04:00:00+00:00 | 2024-08-07T04:00:00+00:00 | time_stop | -1071.5606 | 12 | False |
| 4 | AVAX/USDT:USDT | long | 2024-11-12T08:00:00+00:00 | 2024-11-12T12:00:00+00:00 | hard_stop | -546.1711 | 1 | False |
| 2 | DOGE/USDT:USDT | short | 2024-08-05T04:00:00+00:00 | 2024-08-06T12:00:00+00:00 | regime_exit | -529.2232 | 8 | False |
| 5 | AVAX/USDT:USDT | short | 2025-02-03T04:00:00+00:00 | 2025-02-03T16:00:00+00:00 | hard_stop | -484.8904 | 3 | False |
| 4 | DOGE/USDT:USDT | long | 2024-11-12T08:00:00+00:00 | 2024-11-12T12:00:00+00:00 | hard_stop | -462.5295 | 1 | False |
| 4 | ETH/USDT:USDT | long | 2024-11-13T16:00:00+00:00 | 2024-11-14T12:00:00+00:00 | hard_stop | -458.0334 | 5 | False |
| 4 | LINK/USDT:USDT | long | 2024-11-11T20:00:00+00:00 | 2024-11-13T00:00:00+00:00 | hard_stop | -432.98 | 7 | False |
| 1 | DOGE/USDT:USDT | short | 2024-07-05T08:00:00+00:00 | 2024-07-06T00:00:00+00:00 | hard_stop | -380.549 | 4 | False |

## Next Candidate

| name | scope | live_validation |
| --- | --- | --- |
| LEAVE_HURST_MTF_FAMILY | V3 was the planned cost-robust follow-up and still failed strict gates; stop adding filters to this family and test a different alpha family. | Do not micro-live this family unless a future independent candidate first passes strict research gates. |
