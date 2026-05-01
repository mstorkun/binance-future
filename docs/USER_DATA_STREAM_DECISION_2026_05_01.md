# User Data Stream Decision 2026-05-01

Status: closes P0 #26 as an architecture decision and live gate. This does not
approve live trading.

Sources checked on 2026-05-01:

- Binance USD-M Futures user data stream connect:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams>
- Binance USD-M Futures start listenKey:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Start-User-Data-Stream>
- Binance USD-M Futures keepalive:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Keepalive-User-Data-Stream>
- Binance USD-M Futures order update event:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Event-Order-Update>

## Decision

REST polling alone is rejected as sufficient for live funds.

Reason: a hard stop can fill or be canceled between hourly bot loops. Without a
user-data stream, local `live_state.json` can remain wrong until the next poll,
and the bot can trail, recover, or open based on stale state.

Therefore:

- `config.USER_DATA_STREAM_REQUIRED_FOR_LIVE = True`
- `config.USER_DATA_STREAM_READY = False`
- if `config.TESTNET=False`, `data.make_exchange()` blocks live exchange
  creation unless the stream gate is marked ready.

This is a no-go gate, not a completed stream implementation.

First implementation layer added:

- [USER_STREAM_LISTEN_KEY_2026_05_01.md](USER_STREAM_LISTEN_KEY_2026_05_01.md)
  adds listenKey start/keepalive URL state helpers.
- [USER_STREAM_EVENT_PARSER_2026_05_01.md](USER_STREAM_EVENT_PARSER_2026_05_01.md)
  parses `ORDER_TRADE_UPDATE` payloads and records them into local
  `order_events.jsonl` telemetry.

The stream runner, keepalive loop, reconnect handling, and live-state
reconciliation are still missing.

## Required Stream Design Before Live

Before `USER_DATA_STREAM_READY` can become `True`, the repo needs a real
testnet-proven implementation:

1. Create/extend a USD-M Futures `listenKey`.
2. Connect to the private user stream WebSocket.
3. Keep the listenKey alive before the 60-minute expiry window.
4. Reconnect before or after the 24-hour connection lifecycle.
5. Order events by event time `E` where needed.
6. Parse `ORDER_TRADE_UPDATE`.
7. Persist order updates into `order_events.jsonl`.
8. Reconcile FILLED, PARTIALLY_FILLED, CANCELED, EXPIRED, liquidation, and ADL
   events against `live_state.json`.
9. Trigger immediate local state refresh when a reduce-only stop fills.
10. Prove behavior on testnet with a small explicitly approved probe.

## Current Runtime Evidence

`ops_status.py --json` now includes:

```json
"user_data_stream": {
  "ok": false,
  "required_for_live": true,
  "ready": false,
  "reason": "user_data_stream_not_ready"
}
```

That failing status is expected in the current paper/testnet research state. It
is a deliberate live-trading block.

## Verification

- `python -m py_compile config.py data.py ops_status.py tests\test_safety.py`
- `python -m pytest -q` -> `73 passed, 3 subtests passed`

No real testnet or live orders were sent for this change.
