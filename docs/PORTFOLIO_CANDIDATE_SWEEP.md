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

Important sweep caveat: all top 30 rows included `TRX/USDT`. The sweep alone
was not activation evidence; the follow-up validation below was required before
changing `config.SYMBOLS`.

## Candidate Validation Follow-Up

Candidate:

```text
DOGE/USDT,LINK/USDT,TRX/USDT
```

Validation was run with `config.SYMBOLS` overridden in memory and CSV writes
guarded, so tracked result CSVs were not overwritten.

Walk-forward result:

| Periods | Positive fixed periods | Avg test return | Worst test return | Worst peak DD | Test trades |
|---:|---:|---:|---:|---:|---:|
| 7 | 7/7 | 20.12% | 5.25% | 5.05% | 155 |

Monte Carlo result, `growth_70_compound`, `5000` iterations, block size `5`:

| Method | Ending p05 | Ending p50 | Ending p95 | Loss probability | Peak DD p95 | Peak DD max |
|---|---:|---:|---:|---:|---:|---:|
| Shuffle | 11301.80 | 11301.80 | 11301.80 | 0.00% | 5.97% | 9.37% |
| Bootstrap | 6742.37 | 11061.41 | 20447.74 | 0.00% | 6.58% | 19.87% |
| Block bootstrap | 6191.14 | 10685.20 | 20594.79 | 0.00% | 6.25% | 11.77% |

Bias audit:

```bash
python bias_audit.py --symbol DOGE/USDT --years 1 --sample-step 96
python bias_audit.py --symbol LINK/USDT --years 1 --sample-step 96
python bias_audit.py --symbol TRX/USDT --years 1 --sample-step 96
```

All three returned `OK - no indicator drift detected`.

Decision: `config.SYMBOLS` uses `DOGE/USDT`, `LINK/USDT`, `TRX/USDT` as the
paper/testnet candidate. Live trading remains blocked by `TESTNET = True` and
`LIVE_TRADING_APPROVED = False`.

## Rules

- This tool must not change `config.SYMBOLS` automatically.
- Treat the output as research only.
- Any winning candidate must pass portfolio walk-forward and Monte Carlo before
  paper/testnet/live wiring.
