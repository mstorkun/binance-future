# Multi-Symbol Test Results

**Question:** Is the Donchian breakout strategy specific to BTC, or is it a general edge?

**Method:** 3-year backtest + walk-forward on BTC, ETH, SOL, BNB using the same parameter set.
The plain backtest and walk-forward use historical funding data; if the data cannot be fetched, the fallback assumption is used.

---

## 1. Plain Backtest (3 years, same parameters)

```
symbol     trades  win_rate  total_pnl   max_dd  pnl_pct  pnl_dd
BTC/USDT       86    %55.8      +76.03    54.25    %7.60    1.38
ETH/USDT       77    %63.6     +243.94    39.81   %24.39    5.98  ← strong
SOL/USDT       90    %72.2     +473.80    71.70   %47.38    6.52  ← very strong
BNB/USDT       70    %57.1      +79.11    63.52    %7.91    1.23
```

**Summary:**
- 4/4 symbols with positive PnL ✓
- Average PnL: +218 USDT/symbol (3 years)
- Strongest: SOL (+47% return)
- Weakest: BTC, BNB (+6-7% return)

---

## 2. Walk-Forward (4 symbols × 7 periods = 28 test windows)

Each period: 18 months train + 3 months test, 3 months roll.

```
symbol     periods  train_avg  test_avg  test_total  test_pos  pos_ratio  test_dd_avg  overfit
BTC/USDT         7    +176.9   -13.2       -92.59        3       42.9%      38.3       +190
ETH/USDT         7    +167.8    +5.0       +35.24        4       57.1%      17.7       +163
SOL/USDT         7    +243.9   +13.7       +96.07        5       71.4%      17.2       +230
BNB/USDT         7    +110.8    +6.8       +47.71        4       57.1%      23.1       +104
```

**Summary:**
- Test average is POSITIVE in 3/4 symbols (only BTC is negative)
- 16 of 28 periods are positive (57%)
- Most reliable: **SOL** (5/7 periods positive, +13.7 average, lowest DD)
- Worst: **BTC** (3/7 periods positive, -13.2 average)

---

## 3. Interpretation

### Good news

- Donchian breakout is **not** specific to BTC — positive on all 4 symbols
- ETH/SOL/BNB perform better than BTC (trends are more persistent in altcoins)
- SOL is particularly strong: 71% positive periods, average +13.7 USDT/period

### Bad news

- BTC alone is not enough — overfitting is very high (+183 gap)
- The train>test gap is large across all symbols (overfitting present)
- DD increases in test periods (avg 18-39 USDT)

### Net Conclusion

> **The strategy may carry a real edge**, but the evidence is not yet conclusive.
> BTC is weak; SOL/ETH are more promising. For a live decision, parameter stability,
> Monte Carlo, and testnet/paper results should be awaited.

---

## 4. Recommendations

### Option A — SOL bot (strongest symbol)
```python
# config.py
SYMBOL = "SOL/USDT"
```
Backtest: +474 USDT, WF: 5/7 positive. However, SOL volatility is high and slippage may be worse.

### Option B — Portfolio: ETH + SOL + BNB
Split 1000 USDT across 3 symbols (333 USDT/symbol). Diversification advantage.
- Plain backtest average: (+244 + 474 + 79) / 3 ≈ +266 USDT/symbol (3 years)
- Correlation risk: crypto coins are ~0.85 correlated to each other, so real diversification is limited

### Option C — Drop BTC entirely
BTC off the list. Only ETH/SOL/BNB.

**My recommendation: try Option B in the testnet/paper phase** — it's too early for a real-money decision.

---

## 5. Next Test Steps

The strategy has moved from "promising → potentially viable." But the following are still required:

1. **Parameter stability map** — try donchian 18-22, vol 1.3-1.7; is the gradient smooth?
2. **Monte Carlo trade-shuffle** — measure 95% worst-case DD
3. **Multi-symbol bot.py support** — currently single symbol
4. **1-2 months testnet paper trading** — is slippage/funding realistic?
5. **Small live (200 USDT)** — 3-month performance monitoring
