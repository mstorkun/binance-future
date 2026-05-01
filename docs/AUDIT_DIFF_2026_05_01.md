# Audit Diff 2026-05-01

Source: Claude 10-agent report cross-check supplied by the user on 2026-05-01.

Purpose: reconcile Claude's critical audit with Codex's repo-aware triage and
merge the remaining open findings into the live-trading no-go backlog.

## Executive Summary

The two reviews agree on the main decision: this bot must not trade live capital
yet. The strongest confirmed gaps are methodology risk, cost sensitivity,
production order safety, state recovery, and operational controls.

Codex has since closed several original gaps:

- strategy-parameter walk-forward smoke,
- risk-capped parameter walk-forward smoke,
- cost stress replay,
- final holdout smoke,
- persistent order events,
- persistent live/testnet position state,
- margin-mode confirmation path,
- `recvWindow` and time-difference policy,
- file-based alert generation.

Those repairs improve the evidence base, but they do not remove the live-trading
block. The remaining execution and ops issues below are still live blockers.

## Full Agreement

| # | Finding | Claude | Codex | Current action |
|---:|---|---|---|---|
| 1 | Live trading must stay blocked | Yes | Confirmed | Keep `TESTNET=True`, `LIVE_TRADING_APPROVED=False`. |
| 2 | Strategy edge was not proven enough | Yes | Confirmed | Param WF, cost stress, holdout added; still research-only. |
| 3 | DOGE/LINK/TRX selection has cherry-pick risk | Yes | Confirmed risk | Holdout added; candidate sweep now reports test count and Bonferroni alpha; DSR/PBO still open. |
| 4 | Static slippage is optimistic | Yes | Confirmed risk | Cost stress added; live fill review still needed. |
| 5 | Funding model is weak | Yes | Confirmed risk | Adverse funding stress added; better historical validation remains open. |
| 6 | Sharpe/Sortino missing | Yes | Confirmed | Closed for basic reporting: `risk_metrics.py`, `risk_adjusted_report.py`, and candidate sweep Sharpe/Sortino/Calmar fields added. |
| 7 | Test coverage too narrow | Yes | Confirmed | Tests increased to 78 plus 3 subtests, but strategy/risk/order tests remain thin. |
| 8 | Live state was RAM-only | Yes | Confirmed | Persistent state added; full exchange reconciliation remains open. |
| 9 | Trailing SL duplicate reduce-only race risk | Yes | Confirmed risk | Extra reduce-only STOP cleanup added after trailing updates; testnet/user-data validation still needed. |
| 10 | `recvWindow` and time sync missing | Yes | Confirmed gap | `RECV_WINDOW_MS` and ccxt time adjustment added. |
| 11 | Alerting missing | Yes | Confirmed gap | File-based alerts added; external alert channels still open. |

## Partial Agreement Or Nuance

| # | Topic | Claude claim | Codex position | Current status |
|---:|---|---|---|---|
| 12 | Walk-forward | No train selection | Risk-profile train selection existed; strategy-param WF was missing | Strategy-param WF and holdout smoke added. |
| 13 | Monte Carlo IID | Bootstrap is path-independent | Block bootstrap exists but does not model all regimes | Regime/funding/liquidity shock modelling still open. |
| 14 | `priceProtect="TRUE"` | Definitely a bug | Verify on testnet before changing | Testnet stop-order probe still needed. |
| 15 | Margin/position mode | Not handled | Position mode/leverage existed; margin mode was gap | Margin-mode confirmation path added. |
| 16 | `config.py` in git | Secret leak risk | Secrets are env-based, but committed runtime config is still risky | Template/local override pattern open. |
| 17 | Disabled protections | Critical bug | Intentional because prior tests reduced CAGR; live-safe gates still needed | Live safety gates remain open. |

## Newly Merged Open Findings

These were not prominent enough in the first Codex triage and are now merged
into the backlog.

### Closed After Merge

| # | Finding | Closure |
|---:|---|---|
| 18 | No `clientOrderId` / idempotency policy | Closed: entry, hard SL, trailing SL, close, and emergency close now submit deterministic `newClientOrderId`; retry/duplicate paths reuse the same id and reconcile through Binance Futures `origClientOrderId` lookup. Claude follow-up B1/B2 also closed. |
| 19 | `_resolve_market_fill` can treat partial fills as full | Closed: fill resolution now separates requested/filled/remaining quantity, supports `PARTIAL_FILL_POLICY`, and sizes state/SL/rollback from filled quantity only. |
| 21 | End-to-end tick precision audit needed | Closed in code: `hard_stop_from_soft()` no longer rounds to 2 decimals; stop prices pass through exchange tick filters; reduce-only close/emergency-close amounts are normalized through market-lot filters. |
| 33 | No bar-age guard for stale candles | Closed in code: `bot.py` now skips symbol processing when the last closed bar is older than `MAX_CLOSED_BAR_AGE_MULT` times the active timeframe. |
| 34 | Live trade decision snapshot missing | Closed in code: entry candidates, risk blocks, successful opens, and failed opens are written to ignored `trade_decisions.jsonl` with bar, indicator, risk, and order-result context. |
| 35 | No one-command kill switch | Closed in code: `emergency_kill_switch.py` provides dry-run status plus explicitly guarded cancel/close execution using reduce-only market closes and order-event telemetry. |
| 36 | API permission/IP whitelist runbook missing | Closed in docs: `docs/API_KEY_SECURITY_RUNBOOK_2026_05_01.md` defines required key permissions, trusted-IP policy, go-live checks, rotation, and `-2015` triage. |
| 27 | Docs and config disagree on leverage/risk | Closed in code/docs: `config.LIVE_PROFILE` defines `balanced_live_v1`, `data.make_exchange()` blocks live exchange creation on profile mismatch, and `docs/RISK_PROFILE_POLICY_2026_05_01.md` labels the current 10x/%4 config as research-only. |
| 26 | No WebSocket user-data stream | Closed as architecture decision/live gate: REST polling is rejected as sufficient for live funds; `USER_DATA_STREAM_REQUIRED_FOR_LIVE=True` and `USER_DATA_STREAM_READY=False` block live exchange creation until a testnet-proven stream implementation exists. |
| B3 | Trailing SL cancel failure can leave orphan reduce-only stops | Closed in code: after a new trailing SL is created, the bot fetches same-side reduce-only STOP orders and cancels all except the new protected stop. |

### P0 Live Blockers

| # | Finding | Why it matters | Next action |
|---:|---|---|---|
| - | None from the Claude/Codex merged P0 list | Live trading remains blocked by gates and unresolved methodology/P1 work | Keep `TESTNET=True` and `LIVE_TRADING_APPROVED=False`. |

### P1 Engineering And Methodology

| # | Finding | Why it matters | Next action |
|---:|---|---|---|
| 20 | Requirements are unpinned | ccxt behavior can drift under the bot | Add lock file or exact prod constraints. |
| 22 | TWAP is passive shell | Dead safety feature can be misunderstood as active | Either remove from live docs or complete integration. |
| 23 | `trade_executor.py` and duplicate trailing logic | More paths means drift and inconsistent behavior | Refactor after live blockers are closed. |
| 24 | `risk_management.py` is stale/dead risk code | Dangerous formulas may be reused accidentally | Delete or quarantine with documentation. |
| 25 | `exchange_filters.py` cache has no refresh policy | Binance filter changes can stale cached limits | Closed: filter cache now has TTL and explicit refresh helper. |
| 28 | Bias audit artifacts not committed as reports | Claims are hard to reproduce | Commit audit summaries for active symbols. |
| 29 | Pattern weights are tunable and weakly justified | Hidden overfit risk | Pattern-risk ablation harness added; permutation/randomized-weight tests remain future work. |
| 30 | Correlation-aware sizing is open-count based | DOGE/LINK/TRX can be highly correlated | Correlation stress report added; covariance-aware cap still requires side-by-side validation before activation. |
| 31 | CSV append is not atomic/fsynced | Runtime telemetry can corrupt on crash | Add atomic or journaled CSV write path where important. |
| 32 | Paper lock heartbeat not refreshed | Manual restart can be blocked by stale locks | Refresh lock heartbeat or improve stale-lock detection. |

## Codex-Only Context Added

| # | Codex note | Meaning |
|---:|---|---|
| 37 | `account_safety.py` exists | Position mode, leverage, margin mode, and hard-stop checks are now centralized. |
| 38 | `ops_status.py --exchange` exists | Exchange safety checks can run separately from file-only status. |
| 39 | Tests increased | Current test count is 78 plus 3 subtests, but coverage is still not enough for live funds. |
| 40 | Parameter WF includes Donchian exit | Exit period is now part of the selector grid. |

## Current Priority Order

1. Add DSR/PBO or equivalent conservative overfitting controls.
2. Add telemetry atomicity hardening.

## Decision

This audit diff does not approve live trading. It only sharpens the no-go list.
The current repo can continue paper/testnet observation while the P0 blockers
above are addressed.
