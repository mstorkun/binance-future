# Hurst-MTF Cost-Robust V3 Brief - 2026-05-05

Status: research-only candidate. This does not enable paper, testnet, or live execution.

## Why This Variant Exists

Cooldown V2 improved the original Hurst-MTF candidate but did not pass:

- Severe total return improved from `-95.3959%` to `-70.5401%`.
- Positive folds improved from `2/12` to `4/12`.
- Sample stayed sufficient: `381` trades.
- 2024-08-05 crisis alpha stayed positive: `+8586.5838`.
- 2025-10-10 stayed negative: `-70.0999`.
- PBO worsened to `0.4167`, so the selected candidates are still unstable.

The important new clue is cost fragility:

- Cooldown V2 baseline compound return: `+20.5578%`.
- Cooldown V2 severe compound return: `-70.5401%`.

Interpretation: cooldown fixed part of the whipsaw/reentry leak, but the
remaining system is too fragile after realistic adverse costs. The next
variant should not add more indicators. It should reduce low-quality turnover
and require enough expected move to survive severe fees, slippage, and funding.

## V3 Rule Family

Keep V2 cooldown and add cost robustness:

- Keep `loss_cooldown_bars=6`.
- Add a minimum volatility cushion before entry:
  - `expected_move_proxy = ATR / entry_price`.
  - Entry allowed only if `expected_move_proxy >= cost_floor_mult * severe_round_trip_cost`.
- Test `cost_floor_mult` grid: `2.0`, `3.0`, `4.0`.
- Add a minimum signal strength gate from the existing MTF frame:
  - Test `signal_strength_min`: `0.45`, `0.55`, `0.65`.
- Do not change the fixed 8-symbol universe.
- Do not relax any strict gate.

## Strict Gate

Same as Phase A and V2. A pass requires every gate true:

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

The user is correct that backtest is not final proof. If V3 ever passes strict
research gates, the next validation is live-market behavior, staged as:

1. Live Binance futures paper/shadow run using real-time market data.
2. Fill-quality report comparing expected entry/exit prices to observed
   market conditions.
3. Micro-live only after paper/shadow distribution is acceptable.
4. Hard daily loss limit, max drawdown kill switch, and no scale-up until
   live logs match the tested profile.

## Decision

Run V3 only as a research candidate. If V3 fails, stop Hurst-MTF engineering
and switch to a different alpha family instead of adding more filters.
