# Trend Quality Report - 2026-05-04

This is a report-only diagnostic. It does not change entry, exit, sizing,
paper trading, testnet, or live behavior.

Source trades file: `portfolio_trades.csv`

## Overall

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_bars_held |
| --- | --- | --- | --- | --- | --- | --- |
| all | 264 | 83.3333 | 10271.7700 | 0.9449 | 10.1688 | 1.0076 |

## Quality Buckets

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_bars_held |
| --- | --- | --- | --- | --- | --- | --- |
| high | 104 | 81.7308 | 5807.5300 | 1.2776 | 8.2071 | 1.0192 |
| medium | 92 | 86.9565 | 2700.6300 | 0.8366 | 23.3266 | 1.0000 |
| low | 68 | 80.8824 | 1763.6100 | 0.5825 | 10.1129 | 1.0000 |

## Side

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_bars_held |
| --- | --- | --- | --- | --- | --- | --- |
| short | 136 | 83.8235 | 6597.0600 | 0.9666 | 17.8839 | 1.0074 |
| long | 128 | 82.8125 | 3674.7100 | 0.9218 | 6.0368 | 1.0078 |

## Exit Reason

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_bars_held |
| --- | --- | --- | --- | --- | --- | --- |
| soft_sl | 263 | 83.2700 | 10148.1800 | 0.9165 | 10.0584 | 1.0076 |
| hard_sl | 1 | 100.0000 | 123.5900 | 8.4112 |  | 1.0000 |

## Reason Tokens

Only tokens with enough observations are shown.

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_bars_held | coverage_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| daily:aligned | 264 | 83.3333 | 10271.7700 | 0.9449 | 10.1688 | 1.0076 | 100.0000 |
| obv:aligned | 253 | 83.3992 | 9886.3800 | 0.9466 | 9.8645 | 1.0079 | 95.8333 |
| market:trend | 116 | 86.2069 | 6523.5200 | 1.2893 | 9.5256 | 1.0172 | 43.9394 |
| vp:short_below_value | 103 | 89.3204 | 6237.8700 | 1.1669 | 30.3105 | 1.0097 | 39.0152 |
| adx:strong | 111 | 83.7838 | 4374.2200 | 1.0788 | 6.9827 | 1.0180 | 42.0455 |
| funding_window | 131 | 80.9160 | 3906.4300 | 0.7141 | 17.6578 | 1.0000 | 49.6212 |
| adx:trend | 75 | 85.3333 | 3892.4800 | 1.0799 | 22.6057 | 1.0000 | 28.4091 |
| vp:long_above_value | 77 | 87.0130 | 2554.2700 | 0.9583 | 5.2150 | 1.0130 | 29.1667 |
| rsi:cold_short | 36 | 88.8889 | 2478.1700 | 1.3272 | 55.2982 | 1.0278 | 13.6364 |
| vol:elevated | 50 | 96.0000 | 1838.7500 | 0.8463 | 124.1581 | 1.0000 | 18.9394 |
| vp:inside_value | 82 | 71.9512 | 1388.7500 | 0.6473 | 5.6063 | 1.0000 | 31.0606 |
| pattern:contra | 33 | 87.8788 | 1361.5100 | 0.9226 | 11.5217 | 1.0000 | 12.5000 |
| rsi:hot_long | 39 | 79.4872 | 1348.5400 | 1.0620 | 3.3121 | 1.0256 | 14.7727 |
| daily_close | 47 | 78.7234 | 1260.7400 | 0.4888 | 16.8464 | 1.0000 | 17.8030 |
| weekend | 50 | 78.0000 | 1117.6100 | 0.7878 | 2.5790 | 1.0200 | 18.9394 |
| pattern:aligned | 17 | 88.2353 | 1098.8900 | 1.4003 | 3.0816 | 1.0588 | 6.4394 |
| vol:high | 21 | 100.0000 | 889.4200 | 0.7615 |  | 1.0000 | 7.9545 |
| obv:against | 11 | 81.8182 | 385.3900 | 0.9057 | 77.7709 | 1.0000 | 4.1667 |

## Decision

Long/short capability does not remove the need for trend quality. The
system should keep measuring whether strong-trend context actually pays
for whipsaws, fees, slippage, and funding before any filter is promoted
from report-only to active trading behavior.
