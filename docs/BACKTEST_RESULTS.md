# Backtest Results

This report covers the current Donchian breakout architecture. The old EMA crossover results should no longer be used for decision-making.

## Model

- Signal: Donchian breakout.
- Filters: volume, ADX, RSI, 1D EMA50 trend.
- Risk: ATR-based SL, 2% risk per trade, 3x leverage.
- Costs: taker fee, slippage, and funding.

## BTC/USDT Plain Backtest

Latest recorded result:

| Metric | Value |
|---|---:|
| Trades | 86 |
| Win rate | 55.8% |
| Total PnL | +76.03 USDT |
| Max DD | 54.25 USDT |
| 3-year return | 7.60% |
| PnL/DD | 1.38 |

Comment: BTC plain backtest is positive but weak. Since the walk-forward result is negative, this alone is not sufficient justification to go live.

## Multi-Symbol Plain Backtest

Latest recorded summary from `multi_symbol_results.csv`:

| Symbol | Trades | Win Rate | PnL | Max DD | Return |
|---|---:|---:|---:|---:|---:|
| BTC/USDT | 86 | 55.8% | +76.03 | 54.25 | 7.60% |
| ETH/USDT | 77 | 63.6% | +243.94 | 39.81 | 24.39% |
| SOL/USDT | 90 | 72.2% | +473.80 | 71.70 | 47.38% |
| BNB/USDT | 70 | 57.1% | +79.11 | 63.52 | 7.91% |

This plain backtest is 4/4 positive, but a plain backtest alone is not enough. The main decision should be made with walk-forward and live/paper testing.

## Funding Model

`backtest.py` now accepts an optional historical funding series:

- If funding data is available, signed funding is computed based on long/short direction.
- If funding data is unavailable, `config.DEFAULT_FUNDING_RATE_PER_8H` is used as a fallback.
- This fallback is conservative; real funding can sometimes be a cost and sometimes an income.

## Monte Carlo Drawdown

1000 trade-shuffle trials over the existing `backtest_results.csv`:

| Metric | Value |
|---|---:|
| PnL p05 | +76.03 USDT |
| PnL median | +76.03 USDT |
| PnL p95 | +76.03 USDT |
| DD median | 98.46 USDT |
| DD p95 | 160.81 USDT |
| DD max | 225.16 USDT |

Total PnL does not change because the same trade set is shuffled; the real signal is on the drawdown side. While the BTC backtest's historical DD is 54.25 USDT, the sequence risk rises to 160.81 USDT in the 95% scenario. For this reason, live risk should start lower than 2%, or a portfolio/position limit should be added.

## Reproduction

```bash
python backtest.py
python multi_symbol_backtest.py
python monte_carlo.py --trades backtest_results.csv
```

Outputs:

- `backtest_results.csv`
- `multi_symbol_results.csv`
- `monte_carlo_results.csv`
