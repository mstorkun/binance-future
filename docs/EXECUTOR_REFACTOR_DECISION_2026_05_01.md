# Executor Refactor Decision 2026-05-01

Status: resolves the current `trade_executor.py` / TWAP passive-shell decision.

## Decision

Keep `trade_executor.py` and `twap_execution.py` quarantined as research-only
contracts. Do not delete them now, and do not wire them into paper/testnet/live
order flow yet.

## Why Not Delete

- They document the intended future lifecycle shape for partial exits, trailing,
  and sliced execution.
- Existing tests keep their behavior explicit.
- Deleting them would lose a useful design target while not improving current
  live safety.

## Why Not Wire Now

- The bot still lacks a production user-data stream implementation.
- Sliced execution needs fill-by-fill state persistence and recovery.
- Partial exits and trailing updates need exchange-side reconciliation, not only
  bar-level simulation.
- Current overfit-control output weakens the strategy edge claim, so execution
  sophistication is not the bottleneck.

## Current Guardrails

- Both modules are marked `PASSIVE_ONLY = True`.
- Both modules are marked `LIVE_ORDER_FLOW_WIRED = False`.
- Both modules expose `raise_if_live_execution_requested()`.
- Tests assert that `bot.py`, `order_manager.py`, and `paper_runner.py` do not
  import them.

## Reopen Criteria

Revisit this decision only after all of these are true:

1. User-data stream is implemented and testnet-proven.
2. Fill, cancel, partial-fill, and reduce-only stop events are reconciled from
   exchange events.
3. Restart recovery persists every executor lifecycle state.
4. Paper/testnet A/B evidence shows the executor improves net results after
   fees, slippage, and funding.

Until then, these helpers are documentation-backed research code, not live
execution infrastructure.
