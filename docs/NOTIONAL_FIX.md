# Notional Bug Fix — Impact Report

**Date:** 2026-04-30
**Found by:** 5-agent audit round (Agent 1 — Funding Cost Modeling)
**Fix:** `backtest.py:127`

---

## Bug

```python
# WRONG (double counting)
notional = (entry + exit_price) * size

# CORRECT (average × size)
notional = (entry + exit_price) / 2 * size
```

`(entry + exit_price)` is already the **sum** of the two prices. It needs to be divided by 2 for the average notional. Due to the bug:
- Commission (0.08%) was being **deducted 2×**
- Slippage (0.15%) was being **deducted 2×**
- Funding (signed) was being **deducted 2×**

This was systematically suppressing real returns.

---

## Impact — Flat Backtest (3 years)

| Symbol | Before (buggy) | After (fix) | Δ |
|---|---:|---:|---:|
| BTC/USDT | +76.03 | **+249.88** | +173.85 (+229%) |
| ETH/USDT | +243.94 | **+369.30** | +125.36 (+51%) |
| SOL/USDT | +473.80 | **+601.86** | +128.06 (+27%) |
| BNB/USDT | +79.11 | **+207.43** | +128.32 (+162%) |
| **Average** | +218 | **+357** | +64% |

Win rates also went up:
- BTC: 55.8% → **66.3%**
- ETH: 63.6% → **76.6%**
- SOL: 72.2% → **78.9%**
- BNB: 57.1% → **72.9%**

**Interpretation:** Because expenses were inflated 2×, even winning trades looked like losses. The real picture emerged after the fix.

---

## Impact — Walk-Forward (BTC, 7 periods)

| | Before | After |
|---|---:|---:|
| Positive periods | 3/7 | **4/7** |
| Test average | -13.2$ | **-0.6$** |
| Train average | +192 | +292 |
| Train>Test gap | +205 | +293 |

BTC walk-forward got close to break-even but is still marginal.

---

## Impact — Multi-Symbol Walk-Forward (4 symbols × 7 periods)

| Symbol | Before | After |
|---|---|---|
| BTC | 3/7 positive, avg -13$ | **4/7**, avg **-0.6$** |
| ETH | 4/7 positive, avg +5$ | **5/7**, avg **+17$** |
| SOL | 5/7 positive, avg +14$ | **6/7**, avg **+29$** |
| BNB | 4/7 positive, avg +7$ | **6/7**, avg **+40$** |

**Total test windows:**
- Before: 16/28 positive (57%)
- After: **21/28 positive (75%)** ← clear improvement

**Test average (across symbols):** +2.3$ → **+21.4$** (10× increase)

---

## Impact — Monte Carlo (BTC)

| | Before | After |
|---|---:|---:|
| Historical DD | 54$ | 54$ |
| MC DD median | 98$ | **78$** |
| MC DD p95 | 161$ | **129$** |
| MC DD max | 225$ | **199$** |
| MC PnL (fixed) | 76$ | **250$** |

DD p95 went 161 → 129 (dropped from 16% to 13% of capital).

---

## New Verdict

### Positive on 4/4 Symbols
- Flat backtest: 4/4 positive (was already so, but PnL is much higher)
- Walk-forward: test average positive on 3/4 symbols (BTC marginal)
- 75% of total test windows positive

### Still Required
1. **Block-bootstrap MC** — IID assumption violation
2. **Multi-symbol Monte Carlo** — only done on BTC
3. **Parameter stability map** — do nearby parameters also work well?
4. **Production infrastructure** — Telegram, retry, state desync (Agent 5)
5. **Testnet 2 months paper trading**

### Live Decision

The strategy has been upgraded from "promising hypothesis" → **"solid candidate"**:
- Positive PnL on 4 symbols
- 21/28 walk-forward periods profitable
- DD p95 is 13% of capital (acceptable)

But **not live money yet**. The next door is testnet/paper trading.

---

## Reproducibility

```bash
git checkout 5a53f30^      # commit before bug
python backtest.py          # old numbers
git checkout main
python backtest.py          # new numbers (fix applied)
```

All results are in `*_results.csv` files.
