# Timeframe Sweep

Last run: 2026-05-01

Purpose: compare whether the active DOGE/LINK/TRX `growth_70_compound`
portfolio should stay on 4h or move to 2h/1h. The sweep uses the current
strategy and portfolio backtest, including commission, slippage, funding,
fixed-profile walk-forward, and block Monte Carlo.

## Commands

Raw bar-parameter comparison:

```bash
python timeframe_sweep.py --years 3 --timeframes 1h 2h 4h --mc-iterations 2000 --block-size 5
```

Scaled-parameter comparison:

```bash
python timeframe_sweep.py --years 3 --timeframes 1h 2h 4h --mc-iterations 2000 --block-size 5 --scaled-params --out timeframe_sweep_scaled_results.csv --wf-out timeframe_walk_forward_scaled_results.csv
```

The scaled mode multiplies indicator lookbacks for lower timeframes so their
calendar-time horizon remains roughly comparable to the current 4h setup. For
example, a 20-bar 4h Donchian lookback is treated as 80 bars on 1h and 40 bars
on 2h.

## Raw Results

Raw mode keeps the same bar counts across timeframes. This makes 1h/2h much
faster strategies, not just the same strategy sampled more often.

| Timeframe | Trades | CAGR | Peak DD | WF positive | WF worst return | MC p05 ending | MC peak-DD p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1h | 1001 | 3503.00% | 13.82% | 7/7 | 19.73% | 8,392,042.47 | 13.53% |
| 2h | 491 | 276.18% | 9.32% | 7/7 | 8.83% | 23,651.90 | 10.29% |
| 4h | 264 | 126.14% | 5.05% | 7/7 | 0.63% | 6,319.45 | 6.25% |

Interpretation: raw 1h is not deployable evidence by itself. It changes the
real time horizon of the indicators and creates very high compounding and cost
turnover. It should be treated as an overfit/fragility warning until proven in
a stricter test.

## Scaled Results

Scaled mode is the fairer comparison for deciding the base timeframe because it
keeps the existing strategy horizon approximately intact.

| Timeframe | Trades | CAGR | Peak DD | Profit factor | WF positive | WF avg return | WF worst return | MC p05 ending | MC peak-DD p95 | MC peak-DD max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2h | 312 | 161.27% | 10.83% | 4.6262 | 7/7 | 18.65% | 6.48% | 9,472.13 | 12.20% | 19.18% |
| 4h | 264 | 126.14% | 5.05% | 10.1688 | 7/7 | 18.86% | 0.63% | 6,319.45 | 6.25% | 11.51% |
| 1h | 266 | 113.64% | 14.56% | 2.3058 | 6/7 | 6.10% | -8.01% | 3,978.40 | 19.56% | 37.31% |

## Decision

- 1h should not replace 4h now. After horizon scaling, it underperforms 4h,
  has one negative walk-forward period, and has materially worse Monte Carlo
  drawdown tails.
- 2h is the strongest candidate for a future active switch. It improves CAGR,
  total ending equity, worst walk-forward return, and Monte Carlo p05 ending
  equity versus 4h.
- 4h remains the conservative active default until an explicit config change is
  made. It has the lowest observed drawdown and the highest profit factor.

If switching to 2h, do not only change `config.TIMEFRAME`. Also scale the
lookback parameters or add timeframe-aware parameters, then rerun:

```bash
python portfolio_backtest.py
python -m pytest tests/test_safety.py -q
python paper_runner.py --once --reset
```

After the switch, restart the paper runner so it imports the new config.

## Shadow Paper Mode

Use this before changing the active 4h config:

```bash
python paper_runner.py --loop --interval-minutes 60 --tag shadow_2h --timeframe 2h --scale-lookbacks --reset
python paper_report.py --tag shadow_2h
python ops_status.py --tag shadow_2h --json
```

The `shadow_2h` tag writes separate runtime files such as
`paper_shadow_2h_state.json` and `paper_shadow_2h_decisions.csv`. It does not
change active 4h paper files or live/testnet order settings.
