# 5-Agent Audit Report (Round 1)

- **Date:** 2026-04-30
- **Auditors:** Claude Sonnet 4.6 — five parallel agents
- **Status:** Completed; the bulk of the critical bugs were fixed.

---

## Context

The first reported backtest result (3-year BTC 4H, optimised parameters):

- 57 trades · 60% win rate · **+1,016 USDT (≈100% return over 3 years)** · Max DD 385 USDT

This number looked too good. Five agents audited the code and methodology in parallel.

---

## Agent 1 — Strategy Validity

**Findings:**

- The strategy logic is classical (EMA + ADX + RSI); 57 trades over 3 years is statistically thin.
- `strategy.py:26-27` — the *flipped* condition is too strict; if ADX/RSI are not aligned at the exact crossover bar, the signal is missed for the rest of the trend.
- `config.py:31` — RSI_SHORT 30–60 is asymmetric (the long band is 40–70).
- `indicators.py` — should have used Wilder smoothing for ADX/RSI/ATR (instead of plain EMA spans).
- No volume filter, no higher-timeframe confirmation.

**Recommendation:** Apply the Wilder fix and re-run the backtest — the current numbers are misleading.

---

## Agent 2 — Risk Management

**Hazard ranking:**

1. **Critical** — No min-notional / step-size check (`risk.py`); Binance will reject orders.
2. **Critical** — No slippage modelling, no partial-fill handling, no reconnect, no state recovery (`bot.py`).
3. **High** — Max DD of 38% is not acceptable for retail (industry standard is 15–20%).
4. **Medium** — A 3% daily-loss limit conflicts with a 2% per-trade risk (two stops = 4%).
5. **Low** — 3x leverage is safe (BTC 4H rarely shows 33% adverse moves).
6. **Low** — 2% per-trade is at the edge; Kelly suggests 1–1.5%.

**Immediate actions:** Add minQty / minNotional guards, write reconnect / state-recovery, drop risk to 1.5%, drop the daily limit to 2.5%.

---

## Agent 3 — Code Quality

**Top 3 critical findings:**

1. **Wilder vs EMA span** (`indicators.py`) — all indicators were mis-calibrated.
2. **`open_position` was not atomic** (`order_manager.py:23-53`) — if the SL order failed, the position was left unprotected; in addition, two `reduceOnly` orders were stacked.
3. **The bot's open-position check was wrong** (`bot.py:51-54, 79`) — the same symbol could open another position on top.

**Other:**

- 4. No look-ahead bias — clean.
- 11. **`*LEVERAGE` multiplier in PnL was wrong** — leverage only changes margin, the realised PnL is **3x inflated**.
- 7. No network / rate-limit handling, no exponential backoff.
- 8. The testnet URL override is unnecessary — `set_sandbox_mode` is enough.
- 12. `optimize.py` is thread-unsafe (mutates module attributes at runtime).

---

## Agent 4 — Backtest Methodology

**Real or illusion?**

| Item | Impact |
|---|---|
| Commission (taker 0.04% × 2) | -91 USDT |
| Slippage (5–15 bps) | -23 USDT |
| Spread | -6 USDT |
| **Total costs** | **≈ -120 USDT** |
| Look-ahead bias | None ✓ |
| Intra-bar ordering | Optimistic bias (high/low order assumed) |
| Overfitting | 108 combinations tested → top pick = classic selection bias |
| Survivorship | BTC only, 4H only |
| Regime mix | 2023 sideways, 2024 bull, 2025 correction — profits concentrated in 2024 |

**Approximate corrections:**

- Reported: 1,016 USDT
- Leverage fix: 1,016 ÷ 3 ≈ 339
- After commissions and slippage: 339 - 120 ≈ 220
- After overfitting deflator (30–50%): **≈110–160 USDT (annualised ≈4–5%)**

**Conclusion:** roughly 60% of the figure is real, 40% is illusion.

---

## Agent 5 — Parameter Robustness

**Robustness score: 3/10.**

- The top-10 PnL spans 488–1,016 (108% spread); the gradient is not smooth.
- `trail_giveback = 0.15` clusters in the top results — single-direction grid only, edge-effect risk.
- `trail_activate` flipping from 0.0 to 1.0 doubles PnL (488 → 897); this is a regime change, not a parameter improvement.
- Win-rate swings from 54% to 81% — red flag.
- 57 trades is statistically weak; 95% CI is roughly ±13% on the win rate.
- p-hacking risk: out of 108 combinations, 5–10 are "good" by chance.
- **No walk-forward, no out-of-sample test** — fatal omission.

**Verdict:** "Promising hypothesis," not a deployable system.

---

## Consolidated Action List

The following fixes were applied. Details: [BUGS_FIXED.md](BUGS_FIXED.md).

- ✅ 1. Wilder smoothing (`indicators.py`)
- ✅ 2. Removed the `*LEVERAGE` multiplier from PnL
- ✅ 3. Added commission (0.04% × 2) + slippage (5 bps × 2)
- ✅ 4. Atomic `open_position` with rollback
- ✅ 5. Removed the duplicate SL order
- ✅ 6. Min-notional guard
- ✅ 7. Symbol-aware position check
- ✅ 8. State recovery on bot restart
- ✅ 9. Walk-forward analysis (`walk_forward.py`)

⚠️ Remaining: stepSize check, slippage `priceProtect`, reconnect / backoff, hedge-mode awareness, periodic `exchange.close()`.
