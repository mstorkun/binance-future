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

## 3-Year Candidate Sweep Result

Latest full 3-symbol command:

```bash
python portfolio_candidate_sweep.py --years 3 --min-size 3 --max-size 3 --top 30
```

Compared with the current baseline, the best candidate was materially stronger
in this in-sample portfolio sweep:

| Portfolio | Rank | Trades | Win rate | Final equity | CAGR | Peak DD | Profit factor |
|---|---:|---:|---:|---:|---:|---:|---:|
| DOGE/USDT,LINK/USDT,TRX/USDT | 1 | 264 | 83.33% | 11271.76 | 124.21% | 5.05% | 10.1688 |
| SOL/USDT,ETH/USDT,BNB/USDT | 303 | 244 | 81.97% | 5786.96 | 79.54% | 7.67% | 8.9192 |
| XRP/USDT,LINK/USDT,SUI/USDT | best non-TRX | 241 | 85.89% | 8498.04 | 104.07% | 5.62% | 43.9710 |

Delta of best candidate vs current baseline:

- CAGR: `+44.67` percentage points.
- Peak drawdown: `-2.62` percentage points.
- Final equity: `+5484.80`.
- Trades: `+20`.

Important caveat: all top 30 rows included `TRX/USDT`. Treat this as a strong
research lead, not as activation evidence. Before changing `config.SYMBOLS`,
run portfolio walk-forward and Monte Carlo on the candidate portfolio and check
whether the TRX contribution survives out-of-sample windows and return
resampling.

## Rules

- This tool must not change `config.SYMBOLS` automatically.
- Treat the output as research only.
- Any winning candidate must pass portfolio walk-forward and Monte Carlo before
  paper/testnet/live wiring.
