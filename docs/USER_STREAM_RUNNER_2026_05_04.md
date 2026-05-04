# User Stream Runner 2026-05-04

Status: websocket runner skeleton added. This does not approve live trading and
does not set `USER_DATA_STREAM_READY=True`.

## What Changed

- Added `user_stream_runner.py`.
- Added pinned runtime dependency `websockets==16.0`.
- The runner can:
  - create a Binance USD-M Futures listenKey through `user_stream_client.py`,
  - build the private websocket URL,
  - consume websocket messages with bounded duplicate detection,
  - reject out-of-order order updates per symbol/order key,
  - route `ORDER_TRADE_UPDATE` payloads through `user_stream_runtime.py`,
  - persist parsed updates and reconciliation decisions into order-event
    telemetry,
  - update `live_state` through the existing conservative reconciliation path,
  - keep the listenKey alive when its refresh window is reached,
  - reconnect before the listenKey connection lifecycle limit,
  - record websocket connection errors and retry with capped backoff.

## Commands

Dry run only creates a listenKey and prints the websocket URL. It does not open
the websocket:

```bash
python user_stream_runner.py --dry-run
```

Bounded stream smoke after explicit testnet credentials are configured:

```bash
python user_stream_runner.py --max-messages 5 --stop-after-seconds 300
```

## Still Not Live-Ready

The live gate remains intentionally closed:

- `config.USER_DATA_STREAM_REQUIRED_FOR_LIVE = True`
- `config.USER_DATA_STREAM_READY = False`
- `config.TESTNET = True`
- `config.LIVE_TRADING_APPROVED = False`

Before readiness can change, the runner still needs empirical Binance Futures
testnet evidence:

1. dry-run listenKey response captured,
2. websocket connection and heartbeat observed,
3. duplicate and out-of-order behavior checked against real events,
4. hard stop fill updates proven to remove local `live_state` immediately,
5. partial fill and cancel/expire events observed or simulated with exchange
   parity,
6. startup/restart handoff tested with existing `live_state.json`,
7. runbook added for running the stream beside `bot.py`.

## Verification

- `python -m py_compile user_stream_runner.py tests\test_safety.py`
- `python -m pytest -q` -> `100 passed, 3 subtests passed`

No real Binance testnet or live orders were sent for this change.
