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

## Activation Rule

Do not wire these modules into live/testnet order flow until all three gates
pass:

1. Portfolio backtest is not worse on CAGR, drawdown, and trade count quality.
2. Walk-forward remains positive in the same or better number of windows.
3. Monte Carlo bootstrap/block drawdown is not worse.

The first integration target should be backtest-only. Paper/testnet and live
wiring should come only after a side-by-side report proves the layer is
net-positive.
