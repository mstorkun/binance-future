# User Stream Event Parser 2026-05-01

Status: adds the first code layer for the future USD-M Futures user-data stream
implementation. This does not enable live trading.

Official Binance docs checked on 2026-05-01:

- Connect:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams>
- Start listenKey:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Start-User-Data-Stream>
- Keepalive listenKey:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Keepalive-User-Data-Stream>
- Order update event:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Event-Order-Update>

## Binance Constraints Captured

- A listenKey is valid for 60 minutes unless extended.
- `POST /fapi/v1/listenKey` returns or extends the active listenKey.
- `PUT /fapi/v1/listenKey` extends validity.
- WebSocket path is `/private/ws/<listenKey>`.
- One connection is valid for 24 hours.
- Updates should be ordered by event time `E` where needed.
- Order updates arrive as `ORDER_TRADE_UPDATE` with the order payload under
  `o`.

## Change

Added `user_stream_events.py`:

- validates `ORDER_TRADE_UPDATE`;
- parses symbol, client order id, order id, side, order type, execution type,
  status, filled quantities, prices, commission, realized PnL, reduce-only flag,
  position side, price-protect flag, and expiry reason;
- detects terminal statuses, partial fills, liquidation/ADL client order ids,
  and events requiring immediate reconciliation;
- records parsed events to `order_events.jsonl` through the existing
  `order_events.record()` path.

## Still Missing

This is not the live stream runner. The following remain required before
`USER_DATA_STREAM_READY=True` can be considered:

1. Signed listenKey lifecycle helper.
2. WebSocket client and reconnect loop.
3. Keepalive scheduler before the 60-minute expiry window.
4. 24-hour reconnect handling.
5. Event-time ordering / deduplication.
6. Live-state reconciliation from parsed events.
7. Testnet proof with explicit approval.

## Verification

- `python -m py_compile user_stream_events.py tests\test_safety.py`
- `python -m pytest tests\test_safety.py -q` -> `89 passed, 3 subtests passed`
- `python -m pytest -q` -> `89 passed, 3 subtests passed`
