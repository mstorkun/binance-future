# Methodology Fix — Multi-Symbol Capital Allocation

**Date:** 2026-04-30
**Found by:** Codex (independent second-opinion review)
**Affected:** `multi_symbol_backtest.py`, `docs/MULTI_SYMBOL.md`, `docs/AGENT_REVIEW_3.md`

---

## The Bug

`multi_symbol_backtest.py` was calling `run_backtest()` once per symbol. `run_backtest()` always seeded `balance = config.CAPITAL_USDT` (1000). So:

- BTC backtest started with 1000 USDT
- ETH backtest started with 1000 USDT (separately)
- SOL backtest started with 1000 USDT (separately)
- BNB backtest started with 1000 USDT (separately)

The reports then summed the four PnLs and presented "+1,178 USDT total" as if it came from a single 1000 USDT portfolio split into 4 buckets. **It did not.** The same four PnLs would have been **a quarter of those values** if each symbol had only 250 USDT to risk-size against.

---

## The Fix

`run_backtest(start_balance=...)` parameter added (`backtest.py:53`).

`multi_symbol_backtest.py` now allocates `CAPITAL_USDT / N` per symbol and reports a **portfolio-level** sum.

---

## Corrected Numbers (1000 USDT split across 4 symbols, 250 USDT each)

| Symbol | Start | Trades | WR | PnL | DD | Return |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 250 | 86 | 66.3% | +62.21 | 13.61 | +24.88% |
| ETH | 250 | 77 | 76.6% | +92.37 | 8.83 | +36.95% |
| SOL | 250 | 90 | 78.9% | +150.49 | 16.88 | +60.20% |
| BNB | 250 | 70 | 72.9% | +51.86 | 14.62 | +20.74% |

**Portfolio totals (3-year backtest):**

| Metric | Value |
|---|---:|
| Total starting capital | 1,000 USDT |
| Total PnL (3 yr) | **+356.93 USDT (+35.69%)** |
| **CAGR** | **+10.71%/yr** |
| Conservative summed DD | 53.94 USDT (5.4%) |
| Positive symbols | 4/4 |

---

## Verdict Changes

| Before | After |
|---|---|
| "Strategy carries a real edge" | Edge is real but small |
| 30-60%/yr realistic target (Hybrid Plan) | **10-15%/yr realistic** (3-year compound) |
| GO with refined hybrid | **SUSPENDED — methodology fixes first** |
| 1H + 5x + 3% can hit 50-80%/yr | This claim is no longer supported |
| User's 100%/yr "fantasy" | Confirmed; corrected numbers reinforce this |

A 10.71%/yr CAGR is competitive with a high-yield savings account — not a justification for crypto risk + leverage exposure. **Live deployment must wait until methodology is repaired and the 1H + leverage plan is re-tested under correct accounting.**

---

## Required Methodology Repairs (Codex's list)

1. ✅ **Capital allocation fix** — done in `multi_symbol_backtest.py`.
2. ⏳ **Walk-forward warmup** — each WF segment currently restarts indicator state; the first ~50 bars of every test window have unstable indicators. Need a warmup buffer prepended.
3. ⏳ **CSV columns** — backtest CSVs should record `size`, `notional`, `commission`, `slippage`, `funding` per trade, not just `pnl`. Without these, post-hoc analysis (e.g. cost decomposition, sensitivity) is impossible.
4. ⏳ **Monte Carlo upgrade** — current shuffle preserves total PnL by construction; this is a known limitation. Need:
   - **Bootstrap** (sample with replacement) for PnL CI.
   - **Block bootstrap** (preserve trade-streak structure) for realistic DD distribution.
5. ⏳ **Multi-symbol Monte Carlo** — only BTC currently has MC; ETH/SOL/BNB need it too, plus a portfolio-level MC with correlation-aware shuffling.
6. ⏳ **Walk-forward at 1H** — none exists yet for the proposed hybrid plan; cannot validate the timeframe shift without it.
7. ⏳ **Re-run agent review** — once items 2-6 are done, the 5-agent review should be repeated with corrected data.

---

## Current Position

- **Live deployment: NO.**
- **Testnet/paper: NO** (until corrected backtest justifies the risk).
- **Active phase: methodology repair.**
- **Next milestones:** items 2-6 above.

The architecture, bug fixes, and atomic order management remain valid. The strategy edge claim and the proposed parameter set are **not supported by current data**.
