# Candle Structure Report - 2026-05-04

This is a report-only diagnostic. It tests whether candle length,
density/compression, directional persistence, volume-range correlation,
and symbol return correlation separate better and worse trades.

Source trades file: `portfolio_trades.csv`
Historical data window: `3` years

## Overall

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_confidence | avg_density | avg_symbol_corr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | 264 | 83.3333 | 10271.7700 | 0.9449 | 10.1688 | 1.0966 | 3.7337 | 0.6190 |

## Structure Alignment

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_confidence | avg_density | avg_symbol_corr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| contra | 101 | 84.1584 | 2450.8300 | 0.6156 | 8.1336 | 1.5000 | 4.0580 | 0.6374 |
| neutral | 88 | 86.3636 | 2772.7600 | 0.9020 | 52.1674 | 0.3330 | 3.5686 | 0.6179 |
| aligned | 75 | 78.6667 | 5048.1800 | 1.4387 | 7.9866 | 1.4493 | 3.4908 | 0.5955 |

## Side

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_confidence | avg_density | avg_symbol_corr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| short | 136 | 83.8235 | 6597.0600 | 0.9666 | 17.8839 | 1.0132 | 3.7304 | 0.6344 |
| long | 128 | 82.8125 | 3674.7100 | 0.9218 | 6.0368 | 1.1852 | 3.7372 | 0.6026 |

## Symbol

| segment | trades | win_rate_pct | pnl | mean_return_pct | profit_factor | avg_confidence | avg_density | avg_symbol_corr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LINK/USDT | 98 | 91.8367 | 2624.0200 | 0.7407 | 67.2799 | 0.9653 | 3.7492 | 0.7017 |
| DOGE/USDT | 92 | 88.0435 | 3658.2900 | 0.8260 | 19.0105 | 1.1826 | 3.8215 | 0.7017 |
| TRX/USDT | 74 | 66.2162 | 3989.4600 | 1.3633 | 5.5459 | 1.1635 | 3.6041 | 0.4067 |

## Decision

The candle-structure model is not an active trading rule. Promote it only
after side-by-side backtest, walk-forward, and cost-stress results prove
that it improves net return without hiding overfit.
