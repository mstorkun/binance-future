# 100%/yr Implementation Plan

> User insists on 100%/yr target. Current portfolio CAGR is 10.71%/yr.
> Closing the gap requires a combined approach (A + B + C) and is not
> guaranteed. This document tracks the plan and the realistic outcomes.

## Plan Phases

### Phase 1 — Methodology Repair (Codex's NO-GO blockers)
- [x] Capital allocation fix (done previously)
- [ ] Walk-forward warmup buffer
- [ ] Per-trade CSV columns (size, notional, commission, slippage, funding)
- [ ] True portfolio walk-forward (concurrent positions, capital lock)
- [ ] Bootstrap + block-bootstrap Monte Carlo

### Phase 2 — Strategy Enhancement (path A)
- [ ] New indicators: regime detector (vol cluster + ADX state machine)
- [ ] OBV / volume divergence
- [ ] Funding skew (extreme funding = reversion signal)
- [ ] Hybrid signal: trend-follow when ADX>25, mean-revert when ADX<15
- [ ] Optional ML layer (only if rule-based combo is positive)

### Phase 3 — Higher Frequency (path B)
- [ ] 15-minute config preset
- [ ] Slippage model recalibration (higher base, breakout multiplier)
- [ ] Funding model adjustment (1H ≈ 0.25 funding/trade vs 4H ≈ 1)
- [ ] Re-optimize parameters at 15min

### Phase 4 — Aggressive Sizing with Safeguards (path C)
- [ ] Drawdown circuit breaker (-10/-20/-30% rules)
- [ ] Correlation-aware sizing (3-2-1.5%)
- [ ] Cluster-loss guard (3 symbols hit SL same day → 24h pause)
- [ ] Per-symbol daily PnL cap

### Phase 5 — Validation
- [ ] Backtest all four configurations (current, A, B, C, A+B+C)
- [ ] Portfolio walk-forward each
- [ ] Bootstrap MC each
- [ ] 10-agent review with corrected data

## Expected Outcomes

| Configuration | Realistic CAGR | Max DD | Honest Verdict |
|---|---|---|---|
| Current (4H, 5x, 3%) | 10-15% | 6-10% | Methodology repaired baseline |
| + Hybrid signal (A) | 15-25% | 10-15% | Plausible improvement |
| + 15min (B) | 20-30% | 15-25% | Higher noise tax |
| + Aggressive sizing (C) | 30-50% | 25-40% | Survives, doesn't thrive |
| **All combined** | **40-70%** | **30-50%** | **Stretch goal** |
| User target | 100%+ | -- | **Not technically supported** |

If A+B+C lands at 40-70%/yr with -30 to -50% DD, the user must accept that 100%/yr requires either:
- A bull-market tailwind (free 30-40% extra in a strong year),
- An undiscovered alpha source (unlikely without months of R&D), or
- HFT-grade infrastructure (out of scope for this project).

## Hard Stops

- If methodology repair shows the original edge was an artifact (e.g.
  walk-forward warmup makes test PnL even more negative), the project
  pivots to "no live deployment" and shifts to a different strategy.
- If A+B+C combined still nets <20%/yr after fees, the bot is shelved.

## Status

Phase 1 risk-accounting repair is partly complete:

- Portfolio equity/margin accounting corrected.
- Portfolio sizing aligned with the live bot.
- Bootstrap/block Monte Carlo exists.
- Calendar/news-risk gate exists for new entries.
- News impact scoring exists, including post-news market reaction measurement.
- 10-agent risk optimization selected the **balanced** default profile:
  `5x`, `3%` sleeve risk, `2` max open positions, `3%` daily loss stop.

Latest balanced 3-year portfolio backtest after calendar-risk controls:
`+52.15% total`, `+15.02% CAGR`, `2.71% max DD`.

The 100%/yr target is still not supported. Next gate: portfolio walk-forward with the corrected accounting engine and then a live-safe news watcher.
