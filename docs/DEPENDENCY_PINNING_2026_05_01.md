# Dependency Pinning 2026-05-01

Status: closes the P1 unpinned-requirements item.

## Why

Order recovery depends on `ccxt` Binance Futures behavior, especially
`origClientOrderId` lookup after timeouts or duplicate client-order-id paths.
Using broad lower bounds lets dependency behavior drift without a code review.

## Change

- `requirements.txt` now pins runtime packages exactly:
  - `ccxt==4.5.51`
  - `pandas==3.0.2`
  - `schedule==1.2.2`
  - `python-dotenv==1.2.2`
  - `websockets==16.0`
- `requirements-dev.txt` adds the test dependency:
  - `pytest==9.0.2`
- Unit tests assert requirement lines use exact pins instead of `>=`.

## Policy

Dependency upgrades should be explicit commits. For `ccxt`, rerun at least:

1. `python -m pytest -q`
2. `python testnet_fill_probe.py --simulate-partial-fill --simulate-duplicate-client-order-id`
3. The real testnet duplicate-client-order-id probe when API keys are available
   and the explicit testnet gate is approved.
4. For `websockets`, run a bounded Binance Futures testnet user-stream smoke
   through `user_stream_runner.py` before changing the pin.

## Verification

- `python -m pytest -q` -> `100 passed, 3 subtests passed`
