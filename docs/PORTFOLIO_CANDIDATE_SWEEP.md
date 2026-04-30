# Portfolio Candidate Sweep

Purpose: search for stronger symbol portfolios without changing the main
strategy. The script fetches candidate data once, scores the universe, runs
portfolio backtests on symbol combinations, and ranks results by CAGR and
drawdown.

## Command

Fast smoke:

```bash
python portfolio_candidate_sweep.py --years 1 --symbols SOL/USDT ETH/USDT BNB/USDT --min-size 3 --max-size 3 --max-combos 1 --top 5
```

Fuller search:

```bash
python portfolio_candidate_sweep.py --years 3 --min-size 3 --max-size 5 --top 20
```

The output files are ignored by git:

- `portfolio_candidate_sweep_results.csv`
- `portfolio_candidate_universe.csv`

## Smoke Result

Latest smoke command:

```bash
python portfolio_candidate_sweep.py --years 1 --symbols SOL/USDT ETH/USDT BNB/USDT --min-size 3 --max-size 3 --max-combos 1 --top 5
```

Result:

| Symbols | Trades | Win rate | Final equity | CAGR | Peak DD |
|---|---:|---:|---:|---:|---:|
| SOL/USDT,ETH/USDT,BNB/USDT | 86 | 82.56% | 1562.35 | 56.23% | 7.67% |

## Rules

- This tool must not change `config.SYMBOLS` automatically.
- Treat the output as research only.
- Any winning candidate must pass portfolio walk-forward and Monte Carlo before
  paper/testnet/live wiring.
