# Backtest Results

This report covers the current Donchian breakout architecture **after the notional bug fix** (`backtest.py:127`). Old EMA crossover results should no longer be used for decisions.

## Model

- Signal: Donchian breakout.
- Filters: volume, ADX, RSI, 1D EMA50 trend.
- Risk: ATR-based SL, 2% per-trade risk, 3x leverage.
- Costs: taker commission (0.08% round-trip), slippage (0.15% round-trip), funding (signed, historical).

## BTC/USDT Flat Backtest

Latest result:

| Metric | Value |
|---|---:|
| Trades | 86 |
| Win rate | 66.3% |
| Total PnL | +249.88 USDT |
| Max DD | 54.47 USDT |
| 3-year return | 24.99% |
| PnL/DD | 4.59 |

**Note:** BTC's flat backtest is positive, but its walk-forward average is still near break-even. Do not move BTC alone to live trading.

## Multi-Symbol Flat Backtest

Latest `multi_symbol_results.csv` summary:

| Symbol | Trades | Win Rate | PnL | Max DD | Return |
|---|---:|---:|---:|---:|---:|
| BTC/USDT | 86 | 66.3% | +249.88 | 54.47 | 24.99% |
| ETH/USDT | 77 | 76.6% | +369.30 | 35.36 | 36.93% |
| SOL/USDT | 90 | 78.9% | +601.86 | 67.49 | 60.19% |
| BNB/USDT | 70 | 72.9% | +207.43 | 58.48 | 20.74% |

Flat backtest is 4/4 positive, average +357 USDT/symbol. Walk-forward (see [WALK_FORWARD.md](WALK_FORWARD.md)) and live/paper testing are still required for the live decision.

## Funding Model

`backtest.py` accepts an optional historical funding series:

- If funding data is available, signed funding is computed per long/short direction.
- If funding data is not available, `config.DEFAULT_FUNDING_RATE_PER_8H` is used as a fallback.
- The fallback is conservative; real funding is sometimes a cost, sometimes a credit.

## Monte Carlo Drawdown

5,000 trade-shuffle iterations on the current `backtest_results.csv` (BTC):

| Metric | Value |
|---|---:|
| PnL p05 | +249.88 USDT |
| PnL median | +249.88 USDT |
| PnL p95 | +249.88 USDT |
| DD median | 78.37 USDT |
| DD p95 | 128.69 USDT |
| DD max | 199.37 USDT |

Total PnL is identical because the same trade set is shuffled; the signal sits in the drawdown distribution. BTC's historical DD is 54 USDT while the 95th-percentile sequencing risk is 129 USDT (~12.9% of capital). Live risk should start lower than 2% per trade or include portfolio/position limits.

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
