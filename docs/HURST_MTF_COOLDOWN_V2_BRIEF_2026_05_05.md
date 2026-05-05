# Hurst-MTF Cooldown V2 Brief - 2026-05-05

Status: research-only candidate. This does not enable paper, testnet, or live execution.

## Why This Variant Exists

The Phase A diagnostic did not show a system with no winners. It showed a
system where winners exist but failed entries are repeated too aggressively.

Key diagnostic facts:

- `trailing_stop`: 132 trades, `+25565.9561` PnL.
- `hard_stop`: 124 trades, `-27898.1850` PnL.
- Reentries within 24h after losing `hard_stop/time_stop/regime_exit`: 109 trades, `-8038.1325` PnL.
- Reentries within 24h after profitable `trailing_stop`: 91 trades, `+3678.0203` PnL.

Interpretation: do not suppress winner continuation. Suppress immediate
same-symbol reentry after the market just proved the setup wrong.

## V2 Rule

Add one rule only:

- If a position exits with negative PnL and the exit reason is `hard_stop`,
  `time_stop`, or `regime_exit`, block new entries for the same symbol for
  `6` 4h bars (`24h`).
- Do not block reentry after profitable `trailing_stop`.
- Do not alter the universe, candidate grid, cost stress, PBO check, or strict
  pass gates.

## Strict Gate

Same as Phase A. No gate is relaxed:

- Net CAGR after severe cost stress `>=80%`.
- PBO `<0.3`.
- Walk-forward positive folds `>=7/12`.
- DSR proxy `>=0`.
- Sortino `>=2.0`.
- No symbol over `40%` of positive PnL.
- No month over `25%` of positive PnL.
- Tail capture `50-80%`.
- Crisis alpha positive on `2024-08-05` and `2025-10-10`.
- Sample `>=200` trades.

## Live-Market Validation Path

Backtest is not the final proof. The final proof is live-market behavior, but
live risk must be staged:

1. Full strict historical rerun.
2. Live-market paper/shadow run on real Binance futures feed.
3. Micro-live only after paper/shadow is stable, with hard daily loss limit,
   kill switch, and no scale-up.
4. Scale only after live trade logs match the expected distribution.

## Decision

Run V2 as a full strict research candidate. If it fails, keep it
`benchmark_only` and move to the next alpha family.
