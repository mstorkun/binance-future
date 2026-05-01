# User Stream Runtime Handler 2026-05-01

Status: adds the runtime adapter that a future websocket loop can call for each
`ORDER_TRADE_UPDATE`. This does not open a websocket and does not enable live
trading.

## Change

Added `user_stream_runtime.py`:

- records the raw parsed order update through `user_stream_events`;
- loads current `live_state` positions;
- applies conservative reconciliation decisions from `user_stream_reconcile`;
- persists changed positions with `live_state.save_positions()`;
- records a `user_stream_reconcile_decision` event to `order_events.jsonl`.

## Current Scope

This module is intentionally a single-message handler. It is safe to unit test
without network access and without Binance credentials.

## Still Missing

- WebSocket runner loop.
- Event-time ordering and duplicate suppression.
- Startup REST snapshot reconciliation before stream consumption.
- Explicit testnet proof before `USER_DATA_STREAM_READY=True`.

## Verification

- `python -m py_compile user_stream_runtime.py tests\test_safety.py`
- `python -m pytest tests\test_safety.py -q` -> `94 passed, 3 subtests passed`
- `python -m pytest -q` -> `94 passed, 3 subtests passed`
