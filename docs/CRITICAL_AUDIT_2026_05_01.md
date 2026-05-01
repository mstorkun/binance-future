# Critical Audit 2026-05-01

Source: Claude multi-agent review supplied by the user on 2026-05-01.

This document records the critique and Codex's first-pass triage. It is not a
strategy change and does not approve live trading.

## Executive Decision

The review is directionally useful and should be treated as a live-trading
blocker list, but not every claim is current or equally supported by the repo.

Current decision:

- Do not go live.
- Do not change the active strategy from this report alone.
- Freeze claims of high CAGR as research-only until methodology is repaired.
- Keep the paper runners running, but use the waiting time for safety and
  methodology fixes.

## Claude Review Summary

The supplied report argues:

- The bot should not trade live capital.
- Current CAGR claims are not statistically defensible.
- DOGE/LINK/TRX may be an in-sample symbol selection artifact.
- Walk-forward and Monte Carlo validation need stronger methodology.
- Production safety is not mature enough for unattended Futures trading.
- Realistic 12-month net expectation may be close to flat after fees,
  slippage, funding, and regime changes.

## Codex First-Pass Triage

| Claim | Status | Notes |
|---|---|---|
| Live trading should remain blocked | Confirmed | `config.TESTNET=True`, `LIVE_TRADING_APPROVED=False`; keep this. |
| Strategy edge is not proven | Confirmed | Backtest evidence is research-grade, not deployment-grade. |
| DOGE/LINK/TRX is cherry-picked from candidate sweep | Confirmed risk | It ranked first in an in-sample sweep. Needs holdout and multiple-testing controls. |
| Walk-forward is fake because there is no train selection | Partially true | `portfolio_walk_forward.py` selects risk profile on train, but does not optimize core strategy parameters. We need true parameter walk-forward. |
| Monte Carlo only assumes IID | Partially outdated | Current code has bootstrap and block-bootstrap, but still does not model volatility regime, liquidity shocks, funding spikes, or symbol correlation perfectly. |
| Slippage is optimistic | Confirmed risk | Static slippage is inadequate for breakout bars and thin/fast markets. |
| Funding model is weak | Confirmed risk | Funding needs symbol/time-specific validation and adverse-funding stress. |
| Sharpe/Sortino/DSR/PBO metrics missing | Confirmed | `rg` shows no Sharpe/Sortino implementation. |
| Test coverage is too narrow | Confirmed | Test count improved to 34, but strategy/risk/order lifecycle coverage is still insufficient. |
| RAM-only live state | Confirmed | `bot.py` keeps `active_positions` in memory; restart recovery exists but trailing state can degrade. |
| Liquidation/protections disabled | Confirmed but intentional | These are disabled because prior side-by-side tests hurt performance. They still need safer live-gate treatment. |
| `priceProtect="TRUE"` is definitely a bug | Needs evidence | Binance REST docs show booleans in response and string fields for several order params; this should be verified by `testnet_fill_probe.py`, not changed blindly. |
| Margin/position mode not handled | Partially fixed | Position-mode check and leverage confirmation now exist. Margin-mode set/verify is still missing. |
| Trailing SL race / duplicate reduce-only stop risk | Partially mitigated | Current design creates new SL before canceling old SL, then fetches same-side reduce-only STOP orders and cancels extras. Testnet/user-data validation remains open. |
| `config.py` should not hold secrets | Partially true | API secrets come from env, but active runtime config is still committed. Need template + local override pattern. |
| recvWindow/timesync missing | Confirmed gap | No explicit time sync/recvWindow policy exists. |
| Alerts missing | Confirmed gap | File telemetry exists, but Telegram/email/push alerting is absent. |

## Immediate Blockers

These must be handled before real capital:

1. Persistent live/testnet state.
2. Exchange order event persistence: `ORDER_TRADE_UPDATE`, partial fills,
   fills, cancels, expiry, reduce-only, realized PnL, commission.
3. Startup reconciliation across exchange position, open orders, local state,
   hard stop, and last strategy decision.
4. Margin-mode verification and/or setter.
5. Time sync and `recvWindow` policy.
6. Alerting for stale heartbeat, missing stop, order failure, wrong position
   mode, margin-mode mismatch, leverage mismatch, and daily loss.
7. Realistic slippage/funding stress tests.
8. True parameter walk-forward with holdout and multiple-testing correction.

## Methodology Repair Plan

### M0 - Evidence Freeze

- Treat all current CAGR claims as research-only.
- Add a clear README warning that candidate sweep results are not live
  expectancy.
- Do not use `portfolio_candidate_sweep_results.csv` as deployment evidence by
  itself.

### M1 - Real Walk-Forward

Build a walk-forward that:

- Optimizes strategy parameters only on train windows.
- Applies selected parameters to untouched OOS windows.
- Uses non-overlapping or purged/embargoed windows.
- Records selected parameters per fold.
- Reports degradation from train to test.

Candidate grid:

- Donchian entry period.
- Donchian exit period.
- Volume multiplier.
- ADX threshold.
- RSI extremes.
- ATR stop multiplier.
- Risk profile.

### M2 - Multiple Testing Control

- Separate final 6-month holdout and do not use it for tuning.
- Compare chosen symbols against random portfolios.
- Report rank stability, Bonferroni-style penalty, and probability of backtest
  overfitting.
- Add Deflated Sharpe Ratio or a simpler conservative proxy if implementation
  time is constrained.

### M3 - Cost Stress

- Run results under multiple cost regimes:
  - current static costs,
  - 30 bps round-trip slippage,
  - 60 bps round-trip slippage,
  - adverse funding stress,
  - flash-crash stop gap stress.
- Reject any strategy that only survives the optimistic cost model.

## Production Repair Plan

### P0 - Already Started

- `exchange_filters.py`: Binance `exchangeInfo` validation added.
- `account_safety.py`: one-way position mode and leverage status added.
- `ops_status.py --exchange`: can query account safety without slowing the
  default file-only status command.

### P0 - Still Open

1. Persist live/testnet order events.
2. Persist live active position state.
3. Add startup reconciliation.
4. Add margin-mode verification.
5. Add time sync / `recvWindow`.
6. Add alerts.

### P1

1. Add realistic slippage/funding stress framework.
2. Add strategy/risk unit tests.
3. Add order lifecycle unit tests.
4. Add independent cross-backtest check.
5. Add richer risk-adjusted metrics.

## Specific Notes On Disputed Items

### `priceProtect`

Do not change this blindly. The Binance order API response shows
`priceProtect` as a boolean, while several request parameters in the same API
are documented as strings. The current code sends `"TRUE"`. The correct next
step is a testnet stop-order probe that confirms whether Binance accepts it and
whether the resulting order has `priceProtect=true`.

### Protections Disabled

`PROTECTIONS_ENABLED=False` and `LIQUIDATION_GUARD_ENABLED=False` are real.
However, prior validation found some passive mature-bot protections reduced
CAGR. This does not mean live should run without safety. It means protection
logic needs separate live-safe gates that do not silently distort the strategy.

### Walk-Forward

The harsh critique is correct for strategy-parameter validation. It is not fully
correct for `portfolio_walk_forward.py`, which does train-window risk-profile
selection. Still, that is not enough. We need strategy-parameter walk-forward,
not only risk-profile walk-forward.

## Current Go/No-Go

No-go for live trading.

Allowed work:

- paper/testnet observation,
- safety plumbing,
- methodology repair,
- documentation,
- non-live testnet probes with explicit approval.

Not allowed:

- mainnet trading,
- increasing leverage/risk based on current backtests,
- enabling disabled protection layers in live/paper without fresh validation,
- rewriting strategy from a single review without measured evidence.

## Next Codex Action

Continue the remaining P0 production repair in this order:

1. tick-size precision audit for all live/testnet order prices,
2. WebSocket user-data stream decision and/or reconciliation proof,
3. doc/config go-live risk-profile consistency,
4. stale-bar guard before live signal execution,
5. live trade decision snapshots,
6. emergency kill switch and API-key runbook.

In parallel, begin methodology repair with true parameter walk-forward and a
final holdout.

## Addendum - Audit Diff Merge

Source: `docs/AUDIT_DIFF_2026_05_01.md`.

Since this first-pass audit was written, Codex added parameter walk-forward,
risk-capped walk-forward, cost stress replay, final holdout validation,
persistent order events, persistent live/testnet state, margin-mode handling,
`recvWindow`/time-difference policy, and file-based alerts.

Those repairs reduce several original gaps, but live trading is still blocked.
Closed after the addendum:

1. Deterministic `clientOrderId` / idempotency for entry, hard SL, trailing SL,
   close, emergency close, retry, timeout, and duplicate recovery paths.
   Claude follow-up tightened duplicate detection and switched client-id lookup
   to Binance Futures `origClientOrderId` first, with ccxt fallback using
   `id=None`.
2. Partial-fill handling so `_resolve_market_fill` cannot size state/stops as
   if a partial fill were full.
3. Trailing-SL orphan cleanup after cancel failure: same-side reduce-only STOP
   orders are reconciled after each trailing update, keeping the newly created
   protected stop and canceling extras.
4. Tick precision audit: hard stops no longer use 2-decimal rounding, stop
   orders are normalized through exchange tick filters, and reduce-only
   close/emergency-close amounts are normalized through market-lot filters.
5. Stale-bar guard: `bot.py` skips symbol processing when the last closed bar is
   older than `MAX_CLOSED_BAR_AGE_MULT` times the active timeframe.
6. Trade decision snapshots: entry candidates, risk blocks, successful opens,
   and failed opens are persisted to ignored `trade_decisions.jsonl`.
7. Emergency kill switch: `emergency_kill_switch.py` provides dry-run status and
   explicitly guarded cancel/close execution with reduce-only market closes.

The remaining newly merged live blockers are:

1. Decide and document WebSocket user-data stream architecture before live, or
   explicitly prove polling plus reconciliation is enough.
2. Resolve doc/config risk-profile inconsistency before any go-live profile is
   named.
3. Document API permission scope and IP whitelist requirements.

P1 additions:

- pin production dependencies or add a lock file,
- add exchange-filter cache refresh policy,
- make important CSV telemetry atomic or journaled,
- refresh paper lock heartbeat,
- quarantine stale/dead risk code,
- either remove or complete passive TWAP/executor shells,
- commit bias-audit summaries,
- add pattern-weight ablation tests,
- add correlation stress or covariance-aware risk caps,
- add Sharpe/Sortino/DSR/PBO or equivalent conservative metrics.
