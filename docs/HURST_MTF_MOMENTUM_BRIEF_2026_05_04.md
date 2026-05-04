# Hurst-Gated Multi-Timeframe Momentum — Strategy Brief (2026-05-04)

**Status:** Research design brief, Codex implementation request. Not yet implemented. Does not enable live trading.

**Author:** Claude (review/research). Implementation handed to Codex per role split (Claude=review, Codex=manufacturing).

## Why this candidate

User target is asymmetric: floor = 80% net annual return, ceiling open (potentially several hundred percent in good regimes). This is a **convex payoff profile**: many small losers, occasional large winners. Mean-reversion / carry / market-making families are concave (small wins, large tail losses) and have already been ruled out by Codex strict-gate research:

- Donchian benchmark: DSR proxy `-2.30`, edge not separable from zero.
- Single-exchange funding carry: `0/32` strict pass.
- Predictive funding PoC: `0/42` strict pass.
- Cross-exchange basis: `0/147` exchange-pair rows pass; average net `-14% APR` after costs.
- Liquidation hunting OHLCV proxy: `0/3` strict pass, insufficient sample.
- Adaptive ML model on 60d: `-88% CAGR`, profit factor `0.86`.

Trend-following with proper regime gating and volatility targeting is the family with documented convex retail edge in crypto and the only family that historically produced multi-hundred-percent years for systematic CTA-style funds. It is also the family Codex has not yet tested with `Hurst gate + MTF confluence + vol target` together.

## Edge thesis

Three independent sources of empirical support:

1. **Hurst exponent gating.** Rolling Hurst > 0.55 marks regimes where price exhibits persistent trend behavior. In regimes with `H < 0.5`, classic Donchian/MACD systems produce whipsaw losses. A Hurst gate is documented to reduce false breakouts by 40-60% in BTC 4h studies (Macrosynergy, Harbourfront).
2. **Multi-timeframe confluence.** Requiring 1d trend, 4h structure, and 1h trigger to all agree filters most chop. Reported false-breakout rejection rate ~60% (QuantPedia BTC MTF studies). This compresses trade count but lifts per-trade expectancy.
3. **Volatility targeting.** Sizing each position to a constant annualized volatility target (e.g. 60%) instead of fixed-fraction risk:
   - reduces drawdown by ~40% vs fixed-fractional sizing (Man Group, Concretum studies),
   - automatically de-leverages in high-vol regimes (October 2025 cascade type events),
   - automatically up-leverages in low-vol trend regimes (where convex upside lives).

Combined: Hurst gate filters when, MTF confluence filters where and which side, vol target filters how much. None alone produces edge sufficient for the user's target. The combination is the candidate.

## Architecture

```
data layer (existing):       data.py, exchange_filters.py
universe (new):              hurst_universe.py     (8-perp curated basket)
regime layer (new):          hurst_gate.py         (rolling DFA / R/S Hurst)
signal layer (new):          mtf_momentum_signal.py (1d trend + 4h structure + 1h trigger)
risk layer (new):            vol_target_sizing.py  (annualized vol targeting)
risk overlays (existing):    btc_market_leader.py, multi_timeframe_candle.py,
                             macro_event_policy.py, news_direction_policy.py,
                             urgent_exit_policy.py
execution layer (existing):  order_manager.py, user_stream_runner.py,
                             account_safety.py, runtime_guards.py
research harness (new):      hurst_mtf_momentum_report.py
                             (walk-forward + PBO + cost stress + per-symbol attribution)
```

The strategy reuses everything Codex has already built. The new modules are additive only; no existing module needs to change.

## Universe

Initial fixed set (8 USDT-perpetuals, high liquidity, sufficient 3y history):

```
BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT, BNB/USDT:USDT,
XRP/USDT:USDT, AVAX/USDT:USDT, LINK/USDT:USDT, DOGE/USDT:USDT
```

Universe is hardcoded for the first pass, not selected from a sweep, to avoid the cherry-pick bias that broke the previous DOGE/LINK/TRX portfolio. A symbol-level walk-forward with random-portfolio baseline is part of the validation gate before any production promotion.

## Signal definition (concrete)

Per symbol, on every 4h closed bar:

1. **Daily trend filter:** `1d EMA200 slope > 0` for long, `< 0` for short. Computed on closed daily bars only, no intra-day leak.
2. **4h structure:** `4h EMA21 vs EMA55` cross with the daily side. ADX(14) on 4h must be `>= 20`.
3. **1h trigger:** `1h close` breaks `1h Donchian(20)` on the same side, with `volume Z-score > 1.5` on the breakout bar.
4. **Hurst gate:** rolling `H(200)` on 4h returns must be `>= 0.55`. Compute via DFA (detrended fluctuation analysis) for stability over R/S.
5. **BTC overlay (existing):** `btc_market_leader.multiplier` must be `>= 0.5` for the side. `block_new_entries` from BTC overlay vetoes.
6. **MTF candle overlay (existing):** `multi_timeframe_candle_decision(side)` permission must be `long_only`/`short_only`/`both_allowed`, not `no_trade`.
7. **Macro/news (existing):** `macro_risk_score < 45` and `news_direction_policy` does not return `block_new_entries`.

All gates AND together. Every gate has an existing implementation except the Hurst gate, the daily trend filter, and the 1h trigger.

## Sizing definition

```
target_annualized_vol_per_position = 0.60   # 60% per-position annualized vol
realized_vol_30d = std(log_returns_1h_last_720_bars) * sqrt(24*365)
position_notional = (target_annualized_vol_per_position / realized_vol_30d) * equity
position_notional = min(position_notional, leverage_cap * equity * per_position_max_pct)
```

Per-position notional is then capped by:
- `per_position_max_pct = 0.20` of equity (so 7-10x leverage stays inside liquidation buffer),
- `MAX_POSITIONS_CONCURRENT = 4` so total notional stays inside `4 * 0.20 = 0.80` of equity at full deployment,
- `urgent_exit_policy` applies as account-level kill switch at 30% / 50% adverse.

This is **not** fixed-fractional sizing. Position size moves inversely with realized volatility, so the same target vol produces small positions in high-vol regimes and larger positions in low-vol trend regimes — exactly where convex upside lives.

## Exit definition

1. **Hard SL:** `entry - 2.5 * ATR(14, 4h)` for long, symmetric for short. Borsa-side `STOP_MARKET` reduceOnly with `MARK_PRICE` workingType.
2. **Trailing SL:** activates after `+1R`. Trails at `1.5 * ATR(14, 4h)` distance.
3. **Time stop:** if no `+1R` move in `12 * 4h = 48h`, close position.
4. **Regime exit:** if Hurst drops below `0.45` (anti-persistent), close all positions of that side.
5. **Urgent exit (existing):** `urgent_exit_policy` applies all account-level rules (30% thesis-aware, 50% absolute).

Trailing matters because the convex profile depends on letting winners run. A tight take-profit destroys the asymmetric upside.

## Implementation plan (for Codex)

Phase A — modules (research only, no live wiring):

1. `hurst_gate.py`
   - `rolling_hurst_dfa(returns, window=200) -> pd.Series`
   - `rolling_hurst_rs(returns, window=200) -> pd.Series` (sanity check, lightweight)
   - Unit tests on synthetic series with known Hurst (0.3 mean-reverting, 0.7 trending).
   - Bias audit row written.

2. `mtf_momentum_signal.py`
   - `compute_signal(symbol, df_1d, df_4h, df_1h) -> SignalRow`
   - Returns `side`, `strength`, `gate_reasons`, `is_entry`.
   - All higher-timeframe features come from closed bars only. `df.iloc[-2]` discipline as in existing modules.

3. `vol_target_sizing.py`
   - `position_notional(equity, realized_vol, target_vol, leverage_cap, per_position_max_pct)`.
   - Pure function, deterministic, fully unit-tested.

4. `hurst_mtf_momentum_report.py`
   - Same shape as `liquidation_hunting_report.py` and `cross_exchange_basis_report.py`.
   - Walk-forward folds with non-overlapping test windows + purge/embargo.
   - PBO matrix computed with all parameter candidates per fold.
   - Cost stress: baseline, 30bps slippage, 60bps slippage, 2x funding.
   - Per-symbol attribution (no single symbol may carry >40% of PnL).
   - Per-month attribution (no single month may carry >25% of PnL).
   - Strict pass gate: net CAGR `>= 80%` after severe-cost scenario AND `PBO < 0.3` AND `>= 7/12 fold positive` AND DSR proxy `>= 0`.

Phase B — adaptive integration (only if Phase A passes):

5. Wire `mtf_momentum_signal` features into `adaptive_decision_report.py` so the adaptive ML can learn whether the Hurst gate plus MTF confluence improves long/short/wait predictions.
6. Run side-by-side: pure rule-based Hurst-MTF vs adaptive Hurst-MTF.

Phase C — paper deployment (only if Phase B passes):

7. Add `hurst_mtf_momentum.py` strategy module that consumes the existing signal/risk/execution stack.
8. Paper run for 30+ days minimum, 60+ days preferred.
9. Compare paper PnL distribution vs backtest distribution. If paper Sharpe is >1 standard deviation below backtest Sharpe, abort.

Phase D — live (blocked until):

- Phase C passes,
- All P0 audit blockers from `docs/CRITICAL_AUDIT_2026_05_04_12AGENT.md` are closed,
- `LIVE_TRADING_APPROVED` and `USER_DATA_STREAM_READY` are reviewed by user.

## Validation gates (must all pass before paper)

| Gate | Threshold |
|---|---|
| Net CAGR after severe cost stress | >= 80% |
| PBO (full matrix) | < 0.3 |
| Walk-forward positive fold ratio | >= 7/12 |
| DSR proxy after Bonferroni haircut | >= 0 |
| Sortino ratio | >= 2.0 (downside vol focus, not Sharpe) |
| Per-symbol PnL concentration | no symbol > 40% |
| Per-month PnL concentration | no month > 25% |
| Tail capture | top 5% of trades produce 50-80% of PnL (convex profile check) |
| Crisis alpha | net positive on 2024-08-05, 2025-10-10 cascade days |
| Sample size | >= 200 trades total across walk-forward |

## Risk overlays already in place

The following already-implemented modules will gate this strategy without requiring changes:

- `urgent_exit_policy.py` — 30% thesis-aware, 50% absolute
- `runtime_guards.trading_disabled_flag` — kill switch persistence
- `account_safety` — position mode, leverage, margin, hard-stop checks
- `live_risk_guard` + `live_profile_status` — config gates for live mode
- `macro_event_policy` + `news_direction_policy` — calendar / event gating
- `btc_market_leader` overlay — alt-vs-BTC permission
- `multi_timeframe_candle` overlay — HTF candle gate

The Hurst-MTF strategy reuses all of these as veto layers. It does not weaken any of them.

## Rollout sequence

1. Codex implements Phase A modules.
2. Codex runs `hurst_mtf_momentum_report.py` strict-gate pass.
3. Claude reviews Phase A code and report (per role split).
4. If strict gate passes, Codex proceeds to Phase B.
5. If strict gate fails with `0 pass`, this candidate joins the `benchmark_only` graveyard and the next candidate (mean-reverting reversal at HTF support, or vol-breakout) is evaluated.

## Sources

- Macrosynergy — Hurst exponent regime detection: https://macrosynergy.com/research/detecting-trends-and-mean-reversion-with-the-hurst-exponent/
- Harbourfront — Hurst exponent crypto regimes: https://harbourfrontquant.substack.com/p/detecting-trends-and-risks-in-crypto
- QuantPedia — Multi-timeframe trend strategy on Bitcoin: https://quantpedia.com/how-to-design-a-simple-multi-timeframe-trend-strategy-on-bitcoin/
- Man Group — Volatility targeting impact: https://www.man.com/insights/the-impact-of-volatility-targeting
- Research Affiliates — Harnessing volatility targeting: https://www.researchaffiliates.com/content/dam/ra/publications/pdf/1014-harnessing-volatility-targeting.pdf
- Concretum — Position sizing in trend following: https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/
- DFA reference (Peng et al.) for rolling Hurst: https://doi.org/10.1103/PhysRevE.49.1685
- Bailey & López de Prado — PBO and DSR: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659
- Binance USD-M klines reference: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Kline-Candlestick-Data
