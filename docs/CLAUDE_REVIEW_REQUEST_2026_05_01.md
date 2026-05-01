# Claude Review Request 2026-05-01

Role split: Codex implemented the fix; Claude should review.

Follow-up: Claude reviewed commit `e93c2f3`. Codex's response to B1/B2/B3 is
recorded in `docs/CLAUDE_REVIEW_RESPONSE_2026_05_01.md`.

## Scope

P0 #18 and #19 from `docs/AUDIT_DIFF_2026_05_01.md`:

- deterministic `newClientOrderId` / idempotent recovery,
- explicit partial-fill handling in `_resolve_market_fill()`.

## Files To Review

- `order_manager.py`
- `config.py`
- `tests/test_safety.py`
- `testnet_fill_probe.py`
- `testnet_fill_probe_simulation.csv`
- `testnet_fill_probe_simulation.jsonl`
- `docs/AUDIT_DIFF_2026_05_01.md`
- `docs/CRITICAL_AUDIT_2026_05_01.md`

## Review Focus

1. Confirm every real order path in `order_manager.py` uses deterministic
   `newClientOrderId`: entry, hard SL, trailing SL, close, emergency close.
2. Confirm retry/timeout/duplicate paths reuse the same client id and reconcile
   via `fetch_order` / `origClientOrderId`.
3. Confirm partial fills cannot size state, SL, trailing SL, or rollback from
   original requested quantity.
4. Confirm `PARTIAL_FILL_POLICY="abort"` closes only filled quantity and
   `"accept"` carries only filled quantity forward.
5. Look for Binance Futures edge cases around client id length, fetch-by-client
   id behavior, and ccxt exception classes.

## Verification Already Run

- `python -m py_compile order_manager.py testnet_fill_probe.py tests\test_safety.py config.py`
- `python -m pytest -q` -> `56 passed`
- `python testnet_fill_probe.py --simulate-partial-fill --simulate-duplicate-client-order-id --simulation-out testnet_fill_probe_simulation.csv`
- `python ops_status.py --json` -> default 4h paper runner healthy, PID `9400`
- `python ops_status.py --tag shadow_2h --json` -> 2h shadow runner healthy,
  PID `17316`

No real testnet or live orders were sent for this review package.
