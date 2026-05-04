# Cross-Exchange Basis PoC - 2026-05-04

This is a research-only Binance/OKX/Bybit perp funding-spread report.
It does not create an executor, does not transfer collateral, and does
not change paper/testnet/live behavior.

## Method

For each common liquid USDT perpetual, each exchange pair is evaluated
with walk-forward folds. The short/long exchange direction is selected
only from the train window. The test window then measures realized funding
spread after conservative open/close costs and a USDT earn benchmark.

Strict pass gate: at least `3` OOS folds, every fold must pass,
and aggregate net funding must beat the benchmark after costs.

Command: `python cross_exchange_basis_report.py --exchanges binance okx bybit --days 180 --min-quote-volume-usdt 5e+07 --max-symbols 60 --train-samples 45 --test-samples 15 --min-folds 3`

## Result

- Universe symbols: `49`
- Exchange-pair rows: `147`
- Exchange-pair rows with OOS folds: `57`
- Passing exchange-pair rows: `0`
- Fold rows: `171`

| symbol | pair | folds | ok_folds | net_vs_earn_pct | avg_annualized_net_after_cost_pct | avg_positive_spread_ratio_pct | ok | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOT/USDT:USDT | binance/okx | 3 | 0 | -1.6095 | -12.5291 | 64.4444 | False | insufficient_oos_basis_edge |
| DOT/USDT:USDT | binance/bybit | 3 | 0 | -1.7323 | -13.8989 | 46.6667 | False | insufficient_oos_basis_edge |
| BNB/USDT:USDT | binance/okx | 3 | 0 | -1.7377 | -13.8789 | 77.7778 | False | insufficient_oos_basis_edge |
| SUI/USDT:USDT | binance/bybit | 3 | 0 | -1.7425 | -14.0036 | 80.0000 | False | insufficient_oos_basis_edge |
| DOT/USDT:USDT | bybit/okx | 3 | 0 | -1.7832 | -14.4460 | 48.8889 | False | insufficient_oos_basis_edge |
| XRP/USDT:USDT | binance/okx | 3 | 0 | -1.7842 | -14.4597 | 75.5556 | False | insufficient_oos_basis_edge |
| FIL/USDT:USDT | binance/okx | 3 | 0 | -1.7977 | -14.6413 | 51.1111 | False | insufficient_oos_basis_edge |
| SUI/USDT:USDT | binance/okx | 3 | 0 | -1.8082 | -14.6838 | 64.4445 | False | insufficient_oos_basis_edge |
| UNI/USDT:USDT | binance/bybit | 3 | 0 | -1.8087 | -14.6668 | 51.1111 | False | insufficient_oos_basis_edge |
| ETH/USDT:USDT | binance/okx | 3 | 0 | -1.8094 | -14.7070 | 64.4444 | False | insufficient_oos_basis_edge |
| UNI/USDT:USDT | binance/okx | 3 | 0 | -1.8105 | -14.7145 | 46.6666 | False | insufficient_oos_basis_edge |
| LTC/USDT:USDT | binance/okx | 3 | 0 | -1.8105 | -14.7050 | 62.2222 | False | insufficient_oos_basis_edge |
| ADA/USDT:USDT | binance/bybit | 3 | 0 | -1.8127 | -14.8046 | 40.0000 | False | insufficient_oos_basis_edge |
| BTC/USDT:USDT | binance/okx | 3 | 0 | -1.8164 | -14.7853 | 62.2222 | False | insufficient_oos_basis_edge |
| BNB/USDT:USDT | binance/bybit | 3 | 0 | -1.8176 | -14.7761 | 66.6667 | False | insufficient_oos_basis_edge |

## Decision

A pass here would still not be executor approval; it would only justify
deeper work on exchange account constraints, transfer cost, collateral
fragmentation, liquidation math, and fill probes. If pass count is zero,
do not build a cross-exchange basis executor.
