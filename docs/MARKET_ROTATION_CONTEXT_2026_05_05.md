# Market Rotation Context Report - 2026-05-05

Status: diagnostic-only. This does not change paper, testnet, or live behavior.

Source trades file: `portfolio_trades.csv`

Method: annotate each trade with prior closed 4h BTC/ETH leadership context.
The context is shifted to the next 4h bar to avoid lookahead.

## Overall

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_btc_return_pct | avg_eth_minus_btc_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all | 264 | 83.3333 | 10271.77 | 0.9449 | 10.1688 | -0.6265 | -0.2992 |

## Rotation Regime

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_btc_return_pct | avg_eth_minus_btc_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| risk_off_broad | 90 | 88.8889 | 4249.86 | 0.8779 | 6.6978 | -5.7197 | -2.3003 |
| mixed_neutral | 75 | 81.3333 | 2383.32 | 1.0419 | 13.7246 | 0.7567 | -0.8978 |
| eth_alt_leads_up | 57 | 82.4561 | 1605.75 | 0.6805 | 19.2099 | 2.9711 | 4.2422 |
| btc_leads_up | 25 | 84.0 | 687.18 | 1.2388 | 14.0025 | 5.9342 | -2.5962 |
| alt_resilient_down | 15 | 66.6667 | 1350.85 | 1.5146 | 35.0264 | -1.8604 | 1.5985 |
| btc_only_strength | 2 | 50.0 | -5.19 | -0.0864 | 0.1878 | 1.4124 | -2.7512 |

## Rotation Alignment

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_btc_return_pct | avg_eth_minus_btc_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| with_rotation | 159 | 87.4214 | 6756.27 | 0.9221 | 21.3827 | -1.2021 | -0.2917 |
| neutral_rotation | 94 | 77.6596 | 3750.56 | 1.0493 | 15.211 | 0.4324 | -0.5725 |
| against_rotation | 11 | 72.7273 | -235.06 | 0.3829 | 0.5522 | -1.3552 | 1.9281 |

## Side And Regime

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_btc_return_pct | avg_eth_minus_btc_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| short\|risk_off_broad | 85 | 90.5882 | 4712.92 | 0.9704 | 21.7207 | -5.8025 | -2.4563 |
| long\|eth_alt_leads_up | 51 | 82.3529 | 1377.75 | 0.6098 | 17.8635 | 3.1902 | 4.3599 |
| long\|mixed_neutral | 42 | 85.7143 | 1115.45 | 1.0572 | 15.5487 | 1.8521 | -0.3005 |
| short\|mixed_neutral | 33 | 75.7576 | 1267.87 | 1.0225 | 12.4605 | -0.6375 | -1.658 |
| long\|btc_leads_up | 22 | 90.9091 | 671.99 | 1.5132 | 43.1839 | 6.2616 | -2.6169 |
| short\|alt_resilient_down | 8 | 75.0 | 379.47 | 1.2668 | 133.6818 | -2.1188 | 1.7094 |
| long\|alt_resilient_down | 7 | 57.1429 | 971.38 | 1.7977 | 27.3675 | -1.565 | 1.4717 |
| short\|eth_alt_leads_up | 6 | 83.3333 | 228.0 | 1.2813 | 36.1852 | 1.109 | 3.242 |
| long\|risk_off_broad | 5 | 60.0 | -463.06 | -0.6951 | 0.1068 | -4.3122 | 0.3515 |
| short\|btc_leads_up | 3 | 33.3333 | 15.19 | -0.7735 | 1.4114 | 3.5335 | -2.444 |
| long\|btc_only_strength | 1 | 100.0 | 1.2 | 0.0913 | None | 1.1997 | -3.1281 |
| short\|btc_only_strength | 1 | 0.0 | -6.39 | -0.264 | 0.0 | 1.625 | -2.3743 |

## Decision

This is evidence collection only. A rotation gate can be tested in a true
entry-time walk-forward only if these buckets show a stable difference after
costs. It is not an execution permission and does not affect live trading.
