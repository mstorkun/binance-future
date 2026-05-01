# Mature Bot Add-ons

This note captures the non-invasive add-ons inspired by mature bot platforms.
They are intentionally passive by default so the current strategy, trade count,
and backtest profitability stay unchanged until each layer is proven useful.

## Added

- `protections.py`
  - Cooldown after a recent same-symbol close.
  - Global stoploss guard after clustered stop-loss exits.
  - Low-profit pair lock for symbols that recently fail to contribute.
  - Max-drawdown lock based on equity versus peak equity.
  - Default: `config.PROTECTIONS_ENABLED = False`.

- `exit_ladder.py`
  - Optional TP1/TP2 partial-close plan.
  - Breakeven stop after the first filled step.
  - Leaves the remaining runner available for trailing continuation.
  - Default: `config.EXIT_LADDER_ENABLED = False`.

- `bias_audit.py`
  - Recomputes indicators on rolling prefixes.
  - Compares prefix results with full-frame results to catch lookahead or
    recursive drift.
  - CLI example:

```bash
python bias_audit.py --symbol SOL/USDT --years 1 --sample-step 96
```

- `pair_universe.py`
  - Scores candidate pairs by available bars, quote volume, ATR percentage, and
    recent funding cost.
  - Default: `config.PAIR_UNIVERSE_ENABLED = False`.

- `twap_execution.py`
  - Builds deterministic TWAP slice plans for larger orders.
  - Does not place orders.
  - Marked `PASSIVE_ONLY = True`; order-flow wiring must fail explicitly until
    a real fill-quality implementation exists.
  - Default: `config.TWAP_ENABLED = False`.

- `trade_executor.py`
  - Passive lifecycle contract for future Hummingbot-style executor refactor.
  - Models activation, partial exits, breakeven, trailing, and final close.
  - Not wired into live/paper order flow.
  - Marked `PASSIVE_ONLY = True`; it must not be treated as current execution
    logic.

- `ops_status.py`
  - Terminal status report for heartbeat, paper equity, recent decisions,
    recent skips, trades, and errors.

- `mature_bot_compare.py`
  - Side-by-side backtest-only comparison:
    baseline, protections, exit ladder, pair universe, and all add-ons.
  - CLI example:

```bash
python mature_bot_compare.py --years 3
```

## Activation Rule

Do not wire these modules into live/testnet order flow until all three gates
pass:

1. Portfolio backtest is not worse on CAGR, drawdown, and trade count quality.
2. Walk-forward remains positive in the same or better number of windows.
3. Monte Carlo bootstrap/block drawdown is not worse.

The first integration target is `mature_bot_compare.py`. Paper/testnet and live
wiring should come only after a side-by-side report proves the layer is
net-positive.

## Latest Side-by-side Result

Command:

```bash
python mature_bot_compare.py --years 3
```

Result:

| Variant | Trades | Win rate | Final equity | CAGR | Peak DD |
|---|---:|---:|---:|---:|---:|
| baseline | 244 | 81.97% | 5786.96 | 79.54% | 7.67% |
| protections | 235 | 82.13% | 5535.17 | 76.89% | 7.67% |
| exit_ladder | 258 | 82.95% | 5513.67 | 76.66% | 7.67% |
| pair_universe | 244 | 81.97% | 5786.96 | 79.54% | 7.67% |
| all_addons | 249 | 83.13% | 5273.78 | 74.06% | 7.67% |

Verdict:

- Keep `protections.py` passive with the current parameters.
- Keep `exit_ladder.py` passive with the current parameters.
- `pair_universe.py` did not change the selected symbols; all current symbols
  passed the filter.
- Do not enable `all_addons` in paper/testnet/live because it reduced CAGR.
