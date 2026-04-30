# User Request — 2026-04-30 Session

> Snapshot for review by other AIs / engineers. The user wants to push the bot
> toward shorter timeframes and higher returns. Decision pending.

## Current Bot State (commit `1db8023`)

| Parameter | Value |
|---|---|
| Timeframe | 4h |
| Symbols | SOL, ETH, BNB (BTC dropped) |
| Leverage | 3x |
| Per-trade risk | 2% |
| Daily loss limit | 3% (uses **equity**, not free balance) |
| Max open positions | 2 (globally enforced across symbols) |
| SL type | `stop_market` |
| Exit | `market` on trend reversal (10-bar Donchian) or trailing 15% |
| Trailing | 15% giveback once in profit |

**Backtest (3 years, post-notional-fix):**
- Multi-symbol total: +1,178 USDT (~39%/yr) on 1,000 USDT
- Walk-forward: 21/28 windows positive (75%)
- Per symbol: SOL +602, ETH +369, BNB +207 (3 yr)

## User's New Requirements

| # | Request | Bot now | Match |
|---|---|---|---|
| 1 | 1H or shorter timeframe | 4H | ❌ |
| 2 | 10-20% capital at risk | 2%/trade | ❌ |
| 3 | >100% annual return | ~39%/yr proven | ❌ |
| 4 | ≥5x leverage | 3x | ❌ |
| 5 | SL = market order | `stop_market` | ✅ |
| 6 | Sell = **limit** order | market | ❌ |
| 7 | Trailing SL up as trend rises | 15% giveback | ✅ |
| 8 | Sell only after **confirmed** reversal | 1-bar trigger | ❌ |

## My Recommendation (Hybrid Plan)

Realistic, backtest-aligned compromise:

| Parameter | User asked | I recommend |
|---|---|---|
| Timeframe | 1H | **1H** ✓ |
| Leverage | 5x+ | **5x** |
| Per-trade risk | 10-20% | **3%** (4 symbols × 3 = ≤12% portfolio risk) |
| Exit type | limit | **limit + 30min timeout → market** |
| Reversal confirm | "fully sure" | **2-bar Donchian reverse (= 2h confirm on 1H)** |
| Annual target | >100% | **50-80% realistic** |

### Rationale

- 100%/year is unrealistic on 3-year backtest evidence (~39% baseline).
- Higher leverage + risk amplifies **drawdowns** as much as gains; compound
  breaks under repeated -20% hits.
- 50-80%/year is exceptional for crypto and aligns with multi-symbol portfolio
  numbers extended to 1H + 5x leverage.

### Risks of Aggressive Plan (User's Original)

- 5x leverage + 20% risk + 3 losses = ~50% account drawdown
- 1H + market orders + thin liquidity = slippage eats edge
- Limit exits without timeout = stuck in losing position when trend continues
- Walk-forward already shows overfitting; shorter TF amplifies this

## Decision Pending

User said "save first, I'll have other AIs analyze". Implementation paused until verdict from second-opinion review.

## Files to Review

- `bot.py` — multi-symbol portfolio loop
- `strategy.py` — get_signal, check_exit, trailing_stop
- `backtest.py` — Donchian + funding + commission/slippage model
- `docs/MULTI_SYMBOL.md` — symbol comparison
- `docs/WALK_FORWARD.md` — out-of-sample evidence
- `docs/NEXT_STEPS.md` — production gaps (Telegram, reconnect, SQLite, tests)

## Open Questions for Reviewing AIs

1. Is 50-80%/year realistic for 1H Donchian breakout on SOL/ETH/BNB with 5x
   leverage and 3% per-trade risk?
2. Is "limit + 30min timeout → market" the right exit pattern, or is there a
   cleaner alternative?
3. What's the right trend-confirmation logic on 1H? (2-bar reverse? ATR break?
   ADX falling below threshold?)
4. Should `MAX_OPEN_POSITIONS` rise from 2 to 3 if running 1H + 3 symbols?
5. What are realistic Sharpe / Calmar targets for this configuration?
