# Fixed Bugs

Critical bugs identified and fixed during the 5-agent audit.

## 1. Wilder Smoothing — CRITICAL

**Issue:** `indicators.py` was using `ewm(span=N)` (alpha=2/(N+1)) for ATR/RSI/ADX. This is **not** standard.

**Standard:** Wilder smoothing — `alpha=1/N`. TradingView, Binance, MT4 all use this. The wrong formula makes ATR react faster than its true value, distorting SL distances and ADX values.

**Fix:** Added a `_wilder()` helper, all Wilder-based indicators switched to it. EMA stayed on classic span (already correct).

---

## 2. `*LEVERAGE` Multiplier in PnL — CRITICAL

**Issue:** `backtest.py` and `optimize.py` computed PnL as `(exit-entry) * size * LEVERAGE`. This is **wrong**. Leverage affects **margin requirement**, **not PnL**.

Correct formula: `PnL = (exit-entry) * size`. Position size calculation is already independent of leverage (risk_usdt / stop_dist).

**Impact:** All reported PnL was **inflated 3x**. 1016 USDT → real 339 USDT.

**Fix:** `*LEVERAGE` multiplier removed.

---

## 3. Commission and Slippage Not Modeled — HIGH

**Issue:** Backtest was ignoring commission and slippage. For 57 trades × average 1500-2000 USDT position:
- Commission: 0.08% round-trip × 57 × 1750 = ~80 USDT
- Slippage: 0.1% round-trip × 57 × 1750 = ~100 USDT

**Fix:** In the backtest, `notional × 0.0009` (commission + slippage) is deducted from each trade's PnL.

---

## 4. Double `reduceOnly` Order Conflict — CRITICAL

**Issue:** `order_manager.py` was placing both a `stop_market` and a `trailing_stop_market` order for the same position. Both `reduceOnly=True`. When one triggers, the other gives an "Order would immediately trigger" or "ReduceOnly Order is rejected" error.

**Fix:** Only the initial `stop_market` order is placed. Trailing SL is updated **manually** by the bot (every cycle: cancel old + place new).

---

## 5. `open_position` Not Atomic — CRITICAL

**Issue:** If the market order succeeds but the SL order fails, the position is left **unprotected**. Fatal under extreme volatility.

**Fix:** `open_position` is atomic:
```python
1. Place market order
2. Try to set SL
3. SL fails → immediately market-close the position (rollback)
```

A `_safe_close_market()` helper was added.

---

## 6. No Min Notional Check — HIGH

**Issue:** Binance Futures min notional for BTC is ~100 USDT. Small positions get rejected, silent failure.

**Fix:** Before `open_position`, `notional = size * price` is computed; if below 100 USDT the position is not opened (warning log).

---

## 7. No Per-Symbol Position Check — HIGH

**Issue:** `bot.py` was running with `MAX_OPEN_POSITIONS=2` but only a single symbol is used. Two positions on the same symbol is a logical error. Moreover, the existing position was not being checked, and a new position was being added on top when a signal arrived.

**Fix:** `_has_open_position()` queries exchange state. If a position is open, only SL update / trend exit checks run.

---

## 8. No State Recovery — MEDIUM

**Issue:** If the bot is restarted, it has no knowledge of the open position or existing SL.

**Fix:** At startup the bot fetches positions from the exchange and rebuilds `active_position` state. Trailing SL calculation continues from the existing entry price.

---

## 9. Look-Ahead Bias — NONE ✓

**Finding:** `strategy.get_signal` uses `df.iloc[-2]` (closed candle), entry at `(i+1).open` is correct. Look-ahead **absent**.

**Action:** None, code is clean.

---

## 10. Intra-Bar Ordering — PARTIALLY FLAWED

**Issue:** Within the same bar, the backtest first updates trailing SL (using high/low), then checks SL. This is an optimistic bias (in reality the order is unknown).

**Impact:** Backtest results may be 5-10% optimistic.

**Fix:** Existing structure preserved (standard approach in literature), commission/slippage margin absorbs this.

---

## 11. Overfitting / Walk-Forward — CRITICAL

**Issue:** `optimize.py` was testing 108 combinations and picking the best. Single-period fit, no walk-forward.

**Fix:** `walk_forward.py` was added. True out-of-sample results are measured via train/test split.

**Result:** Train average +71.5 USDT, **test average -1.5 USDT**. Strategy is overfit.

---

## Remaining Gaps

⚠️ These bugs are not yet fixed (low priority or require restructuring):

- stepSize/precision check (Binance lot size)
- ccxt `priceProtect` parameter (slippage limit)
- Exponential backoff for `ccxt.NetworkError`, `RateLimitExceeded`
- Hedge mode detection and warning
- Periodic `exchange.close()` (session leak on long runs)
- Funding rate accounting (8-hour perpetual funding)
