# 5-Agent Second Audit — Donchian Breakout Strategy

**Date:** 2026-04-30
**Context:** After the first audit, the strategy was switched from EMA crossover to Donchian breakout.
The initial Donchian results (+632 USDT, walk-forward 3/3 positive) looked too good — out of skepticism
we ran a second agent round.

---

## 1. Strategy Validity — Agent 1

**Score: 6/10**

- Donchian 20-bar is reasonable for BTC 4H, close to Turtle System 1 ✓
- Volume 1.5×MA20 is a moderate filter — Wyckoff standard is a stricter 2.0×
- 1D EMA50 long/short-only creates bias in ranging markets — should be softened
- Trailing 15% is tight (literature suggests 25-30%)
- **ADX is computed but not used** — sideways-market filter is missing

**Recommendations applied:** ADX filter (`config.ADX_THRESH = 20`) added.

---

## 2. Risk Management — Agent 2

**Score: 5/10**

- 2% per trade is very conservative relative to Kelly (Kelly suggests 14-27%)
- 3x leverage keeps liquidation risk near zero ✓
- Don't change trailing 15% — the backtest was built with this parameter
- **`MAX_OPEN_POSITIONS=2` is a dead parameter** (single symbol used)
- Daily limit 3% vs per-trade 2% → 1.5 SL buffer, narrow
- Funding rate is missing from the backtest ❗

**Danger ranking:**
1. Trailing SL race condition
2. Fake SL price during state recovery
3. Funding/commission missing in backtest
4. Turkey Binance account risk

---

## 3. Backtest Methodology & Code — Agent 3

**TOP 3 CRITICAL FINDINGS:**

**[1] CRITICAL — Intra-bar SL/trail ordering bug**
In `backtest.py:48-86`, within the same bar, extreme=high was being updated first and the SL was checked afterwards. The order of high/low within OHLC is unknown — this causes the trailing SL to be moved to a higher level than it should and exits to be recorded with smaller losses. **Typical impact: +5-15% inflated PnL.**

**[2] HIGH — `add_daily_trend` look-ahead risk**
The shift logic in `indicators.py:80` turned out to be correct (`+1 day` makes the 1D bar close valid afterwards), but the comment is insufficient and edge-case tests are missing.

**[3] HIGH — `bot.py:_recover_position` does not query the exchange SL**
After restart it was recomputing the SL from ATR. The bot then updates the trailing from the wrong point.

**Other:**
- Look-ahead Donchian shift(1) ✓ correct
- Backtest entry timing ✓ correct (one-bar delay, intentional/conservative)
- `walk_forward._override` try/finally ✓ present
- Position was being opened even if `set_leverage` failed — abort should be added

---

## 4. Statistical Robustness — Agent 4

**Score: 5.5/10**

- Train +644 vs Test +144 → ratio 22% (acceptable: 40-60%). **Overfitting present but not catastrophic.**
- 75 test trades Wilson 95% CI WR: [56.7%, 77.5%] — wide but above break-even
- 3/3 positive p-value = 0.125 (insignificant)
- One-sample t-test PnL>0: t=4.9, df=2, p≈0.039 — borderline significant, n=3 is weak
- Test DDs 24/68/39 — std 18, worst-case μ+2σ ≈ 80 USDT
- Parameter drift in P3 (20→30) is a **red flag**

**"Promising, not proven."**

**Missing tests:** Monte Carlo trade-shuffle, bootstrap CI, parameter stability map, more WF periods (8+).

---

## 5. Real-World — Agent 5

**Score: 5/10**

**TOP 3 RISKS (will appear live, were invisible in backtest):**

1. **Funding bleed:** BTC perp average 0.01%/8h × 365×3 = 11%/yr ≈ 5-8 percentage points of return evaporate over 3 years
2. **State desync:** fake SL after restart → double SL or wrong SL = large loss
3. **Turkey operational:** account freeze + USDT withdrawal = capital trapped

**Slippage 5 bps insufficient** — at breakout moments 10-30 bps is realistic. 15 bps round-trip should be added to the model.

**Monitoring is zero:** Telegram, healthcheck, heartbeat — none exist.

---

# APPLIED FIXES (critical bugs)

| # | Finding | File | Applied |
|---|---|---|---|
| 1 | Intra-bar SL/trail ordering | `backtest.py` | ✅ SL check moved BEFORE extreme update |
| 2 | Funding rate missing | `backtest.py` | ✅ 0.01%/8h average added (~1 funding/4H bar) |
| 3 | Slippage 5 bps too low | `backtest.py` | ✅ Raised to 15 bps round-trip |
| 4 | Trailing SL race condition | `order_manager.py` | ✅ New order first, then cancel old |
| 5 | Position opens if set_leverage fails | `order_manager.py` | ✅ If False returned, position opening aborted |
| 6 | State recovery fake SL | `bot.py` | ✅ Pulls from exchange via `fetch_active_sl` |
| 7 | ADX filter unused | `strategy.py` | ✅ Early return on `bar["adx"] < ADX_THRESH` |
| 8 | stepSize precision | `order_manager.py` | ✅ `amount_to_precision()` |

---

# BEFORE vs AFTER BUG FIXES

| Metric | Initial Donchian | After bug fixes |
|---|---|---|
| Backtest 3-year PnL | +632 USDT | **+62.50 USDT** |
| Backtest WR | 70.6% | 54.7% |
| Backtest trade count | 126 | 86 (ADX filter) |
| Walk-forward test average | +144 USDT | **+6.8 USDT** |
| 3/3 tests positive | 3/3 | 1/3 |

**Conclusion:** The initial +632 figure **came from optimistic intra-bar bias + missing funding/slippage**. Real strategy performance is much more modest.

---

# CONSOLIDATED VERDICT

The strategy is **NOT ready for live**:
- Annual ~2% net return (3 years, BTC single symbol)
- Walk-forward test average is nearly zero
- Only P1 test is positive

Positives:
- Bugs were found and fixed → backtest is now reliable
- Architecture is solid, atomic order flow works
- Signal quality improved with ADX filter (trade count dropped)

Required next steps:
1. More WF periods (8+, roll 3 months)
2. Parameter stability map
3. Monte Carlo trade-shuffle (DD 95% worst-case)
4. Multi-symbol test (ETH, SOL, BNB)
5. Volume threshold 1.5 → 1.8 trial
6. Trailing 15% → 25% trial

Live capital should not be used without these steps.
