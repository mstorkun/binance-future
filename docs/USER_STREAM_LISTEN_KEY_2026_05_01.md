# User Stream ListenKey Helpers 2026-05-01

Status: adds the listenKey lifecycle helper layer for the future user-data
stream runner. This does not connect to Binance and does not enable live
trading.

Official Binance docs checked on 2026-05-01:

- Connect:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams>
- Start listenKey:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Start-User-Data-Stream>
- Keepalive listenKey:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Keepalive-User-Data-Stream>

## Change

Added `user_stream_client.py`:

- `start_listen_key(exchange)` calls `fapiPrivatePostListenKey()`;
- `keepalive_listen_key(exchange, state)` calls `fapiPrivatePutListenKey()`;
- `listen_key_ws_url()` builds the private websocket URL;
- `ListenKeyState` tracks creation/keepalive age and signals:
  - keepalive after 30 minutes,
  - reconnect before the 24-hour connection lifecycle.

## Important

This helper is intentionally not used by `bot.py` yet. The missing pieces are:

1. WebSocket client loop.
2. Message parser integration with `user_stream_events.py`.
3. Event ordering/deduplication.
4. Live-state reconciliation from parsed events.
5. Testnet proof before `USER_DATA_STREAM_READY=True`.

## Verification

- `python -m py_compile user_stream_client.py tests\test_safety.py`
- `python -m pytest tests\test_safety.py -q` -> `91 passed, 3 subtests passed`
- `python -m pytest -q` -> `91 passed, 3 subtests passed`
