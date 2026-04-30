# Multi-Symbol Test Results

> ⚠️ **PORTFOLIO TOTALS REVISED (2026-04-30)**
>
> Earlier versions of this document presented "+1,178 USDT" as the portfolio
> result. That was a misreading — each symbol had been backtested with its
> own 1000 USDT sandbox, and the four results were summed. With the correct
> shared-capital model (1000 USDT split across 4 symbols at 250 each), the
> realistic portfolio result is **+356.93 USDT over 3 years (CAGR 10.71%/yr)**.
>
> See [METHODOLOGY_FIX.md](METHODOLOGY_FIX.md) for the bug, the fix, and the
> revised verdict.

**Question:** Is the Donchian breakout strategy specific to BTC, or a general edge?

**Method:** 3-year backtest + walk-forward across BTC, ETH, SOL, BNB with the same parameter set. Both flat backtest and walk-forward use historical funding data; if not available, they fall back to the conservative default.

The numbers below reflect the **post-notional-fix + post-capital-allocation-fix** run.

---

## 1. Flat Backtest — Per Symbol (each tested with 250 USDT, 1/4 of total capital)

```
symbol     start  trades  win_rate  total_pnl   max_dd   pnl_pct
BTC/USDT     250      86    66.3%     +62.21    13.61    24.88%
ETH/USDT     250      77    76.6%     +92.37     8.83    36.95%
SOL/USDT     250      90    78.9%    +150.49    16.88    60.20%
BNB/USDT     250      70    72.9%     +51.86    14.62    20.74%
```

**Per-symbol summary:**
- 4/4 symbols positive PnL.
- Strongest: SOL (+60% return on its 250 USDT slice).
- Weakest: BNB and BTC (+21% / +25%).

**Portfolio total (1000 USDT split into 4 × 250):**
- Total PnL (3 yr): **+356.93 USDT (+35.69%)**
- **CAGR: +10.71%/yr**
- Conservative summed DD: 53.94 USDT (5.4%)

---

## 2. Walk-Forward (4 symbols x 7 periods = 28 test windows)

Each period: 18 months train + 3 months test, 3 month roll.

```
symbol     periods  train_avg  test_avg  test_total  test_pos  pos_ratio  test_dd_avg  overfit
BTC/USDT         7    +292.3   -0.6        -3.89         4       57.1%      34.7      +293
ETH/USDT         7    +236.7  +17.3      +121.05         5       71.4%      16.4      +219
SOL/USDT         7    +359.1  +29.1      +203.81         6       85.7%      15.5      +330
BNB/USDT         7    +204.8  +39.7      +277.69         6       85.7%      20.1      +165
```

**Summary:**
- 3/4 symbols have positive average test PnL (BTC borderline).
- 21/28 windows positive (75%).
- Most reliable: **SOL and BNB** (6/7 windows positive).
- Weakest: **BTC** (4/7 positive, average -0.6 USDT — essentially break-even).

---

## 3. Interpretation

### Good news

- Donchian breakout is **not** BTC-specific — it is positive on 4 symbols.
- ETH/SOL/BNB outperform BTC (altcoin trends are more persistent).
- 75% of all walk-forward test windows are profitable.

### Bad news

- BTC alone is not viable as a live target.
- Train > test gap is large on every symbol (overfitting risk remains).
- Test-period DDs are higher than train-period DDs (avg 15-35 USDT).

### Net Conclusion

> **The strategy carries a real edge**, but proof is not yet definitive.
> BTC is weak; SOL/ETH/BNB are more promising. Parameter stability,
> Monte Carlo, and testnet/paper results are still required before going live.

---

## 4. Recommendations

### Option A - SOL only (strongest single symbol)
```python
# config.py
SYMBOL = "SOL/USDT"
```
Backtest: +602 USDT, WF: 6/7 positive. SOL volatility is high; slippage may be worse live.

### Option B - Portfolio: ETH + SOL + BNB (current)
Split 1,000 USDT across 3 symbols (333 USDT each). This is **already implemented** - `bot.py` iterates over `config.SYMBOLS = ["SOL/USDT", "ETH/USDT", "BNB/USDT"]`.
- Approximate combined backtest PnL: +124 + 200 + 69 ≈ **+393 USDT (3 years, ~11.7%/yr CAGR)** — proportional to the 250-USDT-per-symbol numbers above scaled to 333.
- Correlation caveat: crypto coins correlate ~0.85, so true diversification is limited.
- The earlier "+1,178 USDT" claim came from running each symbol with its own 1000 USDT sandbox; that was a methodology bug — see [METHODOLOGY_FIX.md](METHODOLOGY_FIX.md).

### Option C - Drop BTC entirely
BTC excluded; only ETH/SOL/BNB are traded. (Matches current config.)

**Recommendation: Option B / C** — testnet/paper first, then a small live ramp.

---

## 5. Next Test Steps

The strategy moved from "promising hypothesis" -> "solid candidate". Still required:

1. **Parameter stability map** — try donchian 18-22, vol 1.3-1.7; is the gradient smooth?
2. **Monte Carlo trade-shuffle** — done for BTC; pending for ETH/SOL/BNB.
3. ~~Multi-symbol bot.py support~~ — done; bot.py is in portfolio mode.
4. **Testnet 1-2 months paper trading** — is slippage/funding realistic?
5. **Small live (200 USDT)** — 3-month performance review.

## Risk Controls Required Before Live

- `MAX_OPEN_POSITIONS` is now globally enforced across symbols (`bot.py`).
- Daily loss limit uses **equity** (free + margin + unrealized), not free balance.
- Telegram alerts, reconnect/backoff, state-desync detection, log rotation, SQLite trade history are still **missing**. See [NEXT_STEPS.md](NEXT_STEPS.md).
