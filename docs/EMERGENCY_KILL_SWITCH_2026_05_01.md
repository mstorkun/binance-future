# Emergency Kill Switch 2026-05-01

Status: closed in code for P0 #35. This does not approve live trading.

## What It Does

`emergency_kill_switch.py` provides one operational command for emergency
status, order cancellation, and reduce-only position closure.

Default mode is dry-run:

```bash
python emergency_kill_switch.py --json
```

Dry-run queries configured symbols and reports:

- open orders that would be cancelled,
- open positions that would be reduce-only closed,
- testnet/live flags,
- total planned actions and errors.

Execution requires an explicit guard:

```bash
python emergency_kill_switch.py --execute --yes-i-understand --json
```

If `config.TESTNET=False`, the CLI also requires `--allow-live`. That extra flag
is intentional because emergency close orders are still real live orders.

## Safety Properties

- No orders are sent unless `--execute --yes-i-understand` is provided.
- Live config requires `--allow-live`.
- Open orders are cancelled per symbol.
- Position closure uses market `reduceOnly=True`.
- Emergency close orders use deterministic `newClientOrderId` through the shared
  idempotent order path.
- Close quantity is normalized with Binance market-lot filters before submit.
- Actions and failures are written to `order_events.jsonl`.

## Verification

- `python -m py_compile emergency_kill_switch.py tests\test_safety.py`
- `python -m pytest tests\test_safety.py -q` -> `69 passed, 3 subtests passed`
- `python -m pytest -q` -> `69 passed, 3 subtests passed`

No real testnet or live orders were sent for this change.
