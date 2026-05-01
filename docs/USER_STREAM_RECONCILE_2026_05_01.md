# User Stream Reconcile 2026-05-01

Status: adds a conservative local-state reconciliation helper for parsed
user-data stream order events. This does not enable live trading.

## Change

Added `user_stream_reconcile.py`:

- `apply_order_update_to_positions(positions, update)` returns updated positions
  and a decision summary.
- Removes local position state only when the event clearly implies local
  trailing/SL state is unsafe:
  - reduce-only `FILLED`,
  - liquidation/ADL/settlement autoclose client order ids,
  - filled stop/take-profit market order event.
- For non-terminal or partial events, it only marks the existing local position
  with the latest user-stream order status and fill quantities.

## Why Conservative

The helper does not invent new positions from user-stream events because entry
recovery needs ATR, SL, and strategy context. It only removes or marks existing
local state.

## Still Missing

- WebSocket runner.
- Event deduplication and event-time ordering.
- Integration with `live_state.save_positions()`.
- Exchange REST snapshot reconciliation after remove/mark decisions.
- Testnet proof before `USER_DATA_STREAM_READY=True`.

## Verification

- `python -m py_compile user_stream_reconcile.py tests\test_safety.py`
- `python -m pytest tests\test_safety.py -q` -> `93 passed, 3 subtests passed`
- `python -m pytest -q` -> `93 passed, 3 subtests passed`
