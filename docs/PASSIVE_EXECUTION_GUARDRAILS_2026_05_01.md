# Passive Execution Guardrails 2026-05-01

Status: closes the P1 TWAP-shell documentation risk and reduces the executor
drift risk.

## Why

`twap_execution.py` and `trade_executor.py` are useful research contracts, but
neither one is part of the live/testnet order path. Treating them as active
safety or execution features would create false confidence.

## Change

- Both modules now expose `PASSIVE_ONLY = True` and
  `LIVE_ORDER_FLOW_WIRED = False`.
- Both modules expose `raise_if_live_execution_requested()` so accidental live
  wiring fails explicitly instead of silently pretending to be implemented.
- `config.TWAP_ENABLED` is documented as a planner-only flag. It does not affect
  `bot.py` or `order_manager.py`.
- Tests assert that `bot.py`, `order_manager.py`, and `paper_runner.py` do not
  import either passive execution helper.

## Remaining Work

The structural executor refactor is still deferred. Before either helper can be
used in paper/testnet/live order flow, it needs:

1. Fill-quality tests against realistic orderbook/slippage assumptions.
2. State persistence and restart recovery for every slice/lifecycle event.
3. User-data stream reconciliation for fills, cancels, and reduce-only stops.
4. Side-by-side paper evidence that it improves net results after fees and
   slippage.

## Verification

- `python -m py_compile twap_execution.py trade_executor.py tests\test_safety.py`
- `python -m pytest tests\test_safety.py -q` -> `83 passed, 3 subtests passed`
- `python -m pytest -q` -> `83 passed, 3 subtests passed`
