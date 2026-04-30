# 5-Agent Review Round 3 — Hybrid Plan Validation

> ⚠️ **VERDICT SUSPENDED (2026-04-30)**
>
> Codex flagged a critical methodology error after this review was published:
> the multi-symbol backtest was running each symbol with a full 1000 USDT
> sandbox, then summing the four results as if they were a single portfolio.
> When corrected to a real shared-capital test (1000 USDT split across 4
> symbols at 250 USDT each), the realistic outcome is **+357 USDT over 3
> years = ~10.7%/yr CAGR**, not 30-60%/yr.
>
> The "GO with refined hybrid" verdict in this document is therefore
> **suspended**. See [METHODOLOGY_FIX.md](METHODOLOGY_FIX.md) for the
> corrected numbers and revised plan.

**Date:** 2026-04-30
**Trigger:** User request for 1H, 5x, 10-20% risk, 100%+/yr.
Hybrid plan proposed: 1H, 5x, 3% per-trade, 50-80%/yr target.

---

## Agent Verdicts

| # | Domain | Verdict | Score |
|---|---|---|---|
| 1 | Quant Trading | **GO WITH CONDITIONS** | 35-65%/yr realistic |
| 2 | Risk Management | **RISKY but manageable** | Hybrid OK; user plan = 40-60% ruin |
| 3 | Crypto Microstructure | **VIABLE conditional** | Slippage 0.22%, limit 90s timeout |
| 4 | Strategy Design | **2-bar alone insufficient** | Need ATR or ADX co-filter |
| 5 | Behavioral | **HYBRID GOOD** | Lower target to 30-60%/yr |

---

## Refined Hybrid Plan (Consolidated)

| Parameter | Original Hybrid | **Refined** | Source |
|---|---|---|---|
| Timeframe | 1H | 1H | All agents agree |
| Leverage | 5x | 5x | Quant + Risk OK |
| Per-trade risk | 3% | **3% (1 open) → 2% (2 open) → 1.5% (3 open)** | Risk: correlation-aware |
| Annual target | 50-80% | **30-60% honest, 80% stretch** | Quant + Behavioral |
| Slippage model | 0.15% | **0.22% round-trip** | Microstructure |
| Limit exit timeout | 30 min | **90 seconds → market fallback** | Microstructure |
| Trend confirm | 2-bar Donchian | **2-bar Donchian AND (ATR×1.0 ters OR ADX<20)** | Strategy |
| MAX_OPEN_POSITIONS | 2 | **2 (3 only if daily limit raised to 5%)** | Risk |
| Min live capital | 1000 USDT | **3000+ USDT (1000 = paper only)** | Risk |

---

## Critical Additions

### 1. Drawdown Circuit Breaker (Behavioral - HIGH PRIORITY)

```
Equity -10% → per-trade risk auto-drops 3% → 2%
Equity -20% → bot pauses 7 days, Telegram alert, requires human resume
Equity -30% → bot stops, manual review mandatory
```

This is the single highest-value behavioral safeguard. Removes capitulation risk from human hands.

### 2. Portfolio-Level Kill Switch (Risk)

```
Daily portfolio P&L -5% → close all, no trades for 24h
Correlated cluster: SOL+ETH+BNB all hit SL same day → 7-day pause
```

### 3. Correlation-Aware Sizing (Risk)

Crypto correlation ~0.85; "diversification" is illusion. Reduce per-trade risk as concurrent positions increase:

```python
risk_pct = 0.03 if open_count == 0 else \
           0.02 if open_count == 1 else \
           0.015 if open_count == 2 else 0.01
```

### 4. New `check_exit()` (Strategy)

```python
def check_exit(df, side):
    bar  = df.iloc[-2]
    prev = df.iloc[-3]
    atr  = bar["atr"]
    adx  = bar["adx"]
    
    if side == LONG:
        ref = bar["donchian_exit_low"]
        two_bar    = bar["close"] < ref and prev["close"] < ref
        atr_ok     = (ref - bar["close"]) >= atr * 1.0
        trend_dead = adx < 20
        return two_bar and (atr_ok or trend_dead)
    # Short: mirror
```

Exit priority: SL hit → trailing hit → check_exit().

### 5. Limit Exit Logic (Microstructure)

```python
# On reversal confirmed:
limit_price = current_bid (long exit) / current_ask (short exit)
order = create_limit(price=limit_price, reduceOnly=True, timeInForce="GTC")
wait 90 seconds
if not filled:
    cancel order
    create_market(reduceOnly=True)
```

---

## Realistic Performance Forecast

Based on 5-agent consensus:

| Metric | Forecast |
|---|---|
| Annual return | 30-60% (stretch 80%) |
| Sharpe ratio | 0.8-1.1 |
| Calmar | 0.7-1.2 |
| Max drawdown | -25% to -35% |
| Win rate | ~55-65% (1H vs 4H 70%) |
| Profit factor | 1.15-1.30 |
| Months to first -10% DD | 2-4 months (high probability) |

**100%/yr is rejected by all agents.** It requires either fantasy backtest, exceptional bull year, or HFT infrastructure — none apply.

---

## Pre-Live Gating

Before any live capital:

1. ✅ Backtest with refined parameters (slippage 0.22%, funding recalibrated for 1H)
2. ✅ Walk-forward 8+ periods, ≥65% positive windows, Calmar ≥0.7
3. ✅ Drawdown circuit breaker code + tests
4. ✅ Correlation-aware sizing
5. ✅ Telegram alerts (open/close/exception/DD threshold)
6. ✅ Reconnect/backoff for ccxt errors
7. ✅ State desync detection
8. ✅ SQLite trade history
9. ✅ Testnet 4-6 weeks paper trading
10. ✅ Live 200 USDT for 8 weeks before scaling

---

## Implementation Order

If user approves:

| Phase | Task | Complexity |
|---|---|---|
| 1 | Refined `check_exit()` + slippage 0.22% | 30 min |
| 2 | Switch TIMEFRAME=1h, recalibrate parameters | 1 hr |
| 3 | Walk-forward at 1H, validate ≥65% positive | 1 hr |
| 4 | Drawdown circuit breaker + correlation sizing | 1 hr |
| 5 | Limit-exit with 90s timeout | 30 min |
| 6 | Telegram + reconnect + SQLite | 2-3 hrs |
| 7 | Testnet validation 4-6 weeks | (calendar) |

---

## Final Consensus

**GO** on refined hybrid plan with **realistic target 30-60%/yr** and **mandatory drawdown circuit breaker**. Reject the user's 100%/yr ambition as not supported by any data; communicate as "let's prove edge first, scale later".
