# 100%/yr Implementation Plan

> User target evolved from 70%/yr toward uncapped upside in strong trends.
> The bot should not cap profit; it should cap risk. This document tracks the
> validation path.

## Plan Phases

### Phase 1 — Methodology Repair (Codex's NO-GO blockers)
- [x] Capital allocation fix (done previously)
- [ ] Walk-forward warmup buffer
- [ ] Per-trade CSV columns (size, notional, commission, slippage, funding)
- [x] True portfolio walk-forward (concurrent positions, capital lock)
- [x] Bootstrap + block-bootstrap Monte Carlo

### Phase 2 — Strategy Enhancement (path A)
- [ ] New indicators: regime detector (vol cluster + ADX state machine)
- [x] Rolling volume profile: POC / VAH / VAL risk context
- [x] Candle-pattern context as align-only risk quality layer
- [x] Futures flow context wired for live/testnet risk decisions
- [ ] OBV / volume divergence
- [x] Funding skew input for live/testnet risk decisions
- [ ] Hybrid signal: trend-follow when ADX>25, mean-revert when ADX<15
- [ ] Optional ML layer (only if rule-based combo is positive)

### Phase 3 — Higher Frequency (path B)
- [ ] 15-minute config preset
- [ ] Slippage model recalibration (higher base, breakout multiplier)
- [ ] Funding model adjustment (1H ≈ 0.25 funding/trade vs 4H ≈ 1)
- [ ] Re-optimize parameters at 15min

### Phase 4 — Aggressive Sizing with Safeguards (path C)
- [x] Drawdown circuit breaker (-10/-20/-30% rules)
- [x] Correlation-aware sizing, now shared by live bot and backtest
- [ ] Cluster-loss guard (3 symbols hit SL same day → 24h pause)
- [ ] Per-symbol daily PnL cap

### Phase 5 — Validation
- [x] Backtest risk profiles through corrected portfolio engine
- [x] Portfolio walk-forward for growth candidate
- [x] Bootstrap/block MC for growth candidate
- [ ] 10-agent review with corrected data

## Expected Outcomes

| Configuration | Realistic CAGR | Max DD | Honest Verdict |
|---|---|---|---|
| Conservative | 34.37% | 3.87% peak DD | Safe but below target |
| Balanced | 55.42% | 5.78% peak DD | Strong risk-adjusted |
| **growth_70_compound** | **79.54%** | **7.67% peak DD** | Current testnet candidate |
| growth_100_compound | 107.11% | 9.55% peak DD | Higher return, weaker risk quality |
| extreme_10pct+ | 305%+ | 16%+ peak DD | Too aggressive for default |

The selected profile does not cap upside. If a strong trend year produces
100-200%+, trailing exits can allow it. The cap is on risk, not on profit.

## Hard Stops

- If methodology repair shows the original edge was an artifact (e.g.
  walk-forward warmup makes test PnL even more negative), the project
  pivots to "no live deployment" and shifts to a different strategy.
- If A+B+C combined still nets <20%/yr after fees, the bot is shelved.

## Status

Current validation state:

- Portfolio equity/margin accounting corrected.
- Portfolio sizing aligned with the live bot.
- Bootstrap/block Monte Carlo exists.
- Calendar/news-risk gate exists for new entries.
- News impact scoring exists, including post-news market reaction measurement.
- Live bot and backtest now share correlation-aware sizing.
- Rolling volume profile exists as a risk-quality layer.
- Candle-pattern context exists as an align-only risk-quality layer.
- Futures flow context exists for live/testnet risk decisions:
  open interest, taker buy/sell, top trader long/short, mark price and funding.
- Default candidate is **growth_70_compound**:
  `10x`, `4%` portfolio risk, `2` max open positions, `6%` daily loss stop.

Latest corrected 3-year portfolio backtest:
`+478.70% total`, `+79.54% CAGR`, `7.67% peak DD`.

Latest walk-forward: 7/7 positive periods for the fixed growth candidate, 14.34%
average test-period return, 7.67% worst test-period peak DD.

Latest Monte Carlo: 5th percentile ending equity is about 4103-4105 USDT from
1000 USDT under bootstrap/block methods; peak-DD p95 is about 7.2-8.7%
depending on method.

Next gate: run testnet/paper with real fills, order-book guard logs, futures
flow logs, and news watcher in reduce/block mode only.
