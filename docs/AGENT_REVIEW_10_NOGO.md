# 10-Agent Review — NO GO Verdict

**Date:** 2026-04-30
**Reviewer:** Codex (independent second-opinion, 10 specialist domains)
**Outcome:** **NO GO** — methodology must be repaired before any further forward-looking decision.

---

## Per-Agent Findings

### 1. Quant / Statistics
BTC walk-forward has only 7 test windows and 56 test trades. BTC test total = -3.89 USDT, mean = -0.56. Reference: `walk_forward_results.csv:1`.
**Verdict:** Edge is **not** statistically established.

### 2. Portfolio Capital
Critical bug found: each symbol was tested with its own 1000 USDT and the four PnLs were summed as a portfolio. Fixed in `multi_symbol_backtest.py:72` (capital is now `CAPITAL_USDT / N`).
Corrected 4-symbol result: **+356.93 USDT / 3 yr, CAGR 10.71%**. Reference: `docs/METHODOLOGY_FIX.md:39`.

### 3. Binance Futures
Commission, funding, and slippage are now in the model. Notional fix verified at `backtest.py:128`. Still **not modelled**: spread, partial fill, order rejection, liquidation buffer, funding spikes.

### 4. Slippage / Microstructure
Constant 15 bps round-trip slippage at `backtest.py:131` may **understate** breakout-bar slippage on SOL/BNB. Effect grows materially if the bot moves to 1H.

### 5. Walk-Forward
Walk-forward currently re-instantiates indicators on the test slice (`walk_forward.py:80`). The first ~50 test bars run on cold indicators, contaminating OOS results. **Warmup buffer required.**

### 6. Monte Carlo
The current MC only shuffles trade order, so total PnL is invariant by construction; it only quantifies drawdown sequencing. To answer "is the PnL itself reliable?", we need **bootstrap** (sample with replacement) and ideally **block bootstrap** (preserves trade-streak structure).

### 7. Strategy / Chart
Donchian breakout + ADX + RSI + daily-trend filter is a coherent trend-following construct. But if the 4H edge is already small, moving to 1H will increase noise more than signal. The 100%/yr target is **not technically supported**.

### 8. Risk Management
2% per-trade is acceptable; 10-20% is too aggressive. Crypto correlation is high; SOL/ETH/BNB tend to lose together. **Correlation-aware sizing remains required.**

### 9. Live Bot / Execution
The live bot now allocates per-symbol capital (`bot.py:120`) — direction is right. But the backtest does **not** simulate concurrent positions or capital lock-up the way the live bot will execute them. Backtest and live behaviour diverge.

### 10. Documentation / Reliability
The repo correctly diagnoses status in `docs/METHODOLOGY_FIX.md:79`: no live, not even testnet, active phase is methodology repair. The earlier "GO" verdict was suspended at `docs/AGENT_REVIEW_3.md:1`.

---

## Joint Decision

**NO GO.** The bot is not "throw it away" material, but:

- Live deployment: rejected.
- Testnet/paper: rejected.
- 1H + 5x + 100%/yr: **not supported by data**.
- Even 30-60%/yr Hybrid Plan: **not supported**.

## Required Repair Order

1. Fix walk-forward warmup (warmup buffer prepended to test windows).
2. Write a **true portfolio walk-forward** that simulates concurrent positions and capital lock-up.
3. Add per-trade columns to backtest CSV: `size`, `notional`, `commission`, `slippage`, `funding`.
4. Replace Monte Carlo with bootstrap + block-bootstrap.
5. **Only then** re-test the 1H plan.
6. Re-run agent review against corrected data.

## Bottom Line

> If the edge exists at all, it is small. The first goal is not "100%/yr", it is "is our measurement honest?". Methodology before strategy.
