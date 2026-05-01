# Claude Review Response 2026-05-01

Source: Claude review of commit `e93c2f3`.

Decision after Codex follow-up: B1, B2, and B3 are fixed in code and covered by
unit tests. Live trading remains blocked because real testnet duplicate-client
id and partial-fill behavior still need empirical exchange evidence.

## Closed Findings

### B1 - Duplicate Error Classification

Changed `_is_duplicate_client_order_error()` to remove broad numeric-code
classification. The helper now only treats explicit duplicate/already-exists
text as idempotent duplicate recovery. Generic Binance codes such as `-2010`,
`-2027`, and `-4015` are no longer duplicate triggers.

Coverage:

- `test_reject_error_codes_are_not_duplicate_recovery`

### B2 - Fetch By Client Order Id

Changed `_fetch_order_by_client_id()` to prefer Binance Futures raw
`fapiPrivateGetOrder` with `origClientOrderId`. The ccxt fallback now calls
`fetch_order(None, symbol, {"origClientOrderId": cid})`, matching the local
ccxt `4.5.51` implementation where `origClientOrderId` controls the request.

Coverage:

- `test_duplicate_order_id_recognized_and_reconciled`
- `test_fetch_order_by_client_id_uses_none_id_fallback`

### B3 - Orphan Trailing Stop Cleanup

Changed `update_trailing_sl()` to run a same-side reduce-only STOP cleanup
after creating the new stop and attempting to cancel the old one. It keeps the
new stop id and cancels extra same-side reduce-only stop orders.

Coverage:

- `test_trailing_sl_cleanup_cancels_orphan_reduce_only_stops`

## Testnet Evidence Status

Added a real gated duplicate-client-order-id probe:

```powershell
python testnet_fill_probe.py --probe-duplicate-client-order-id-real --approve-testnet-fill
```

This sends real Binance Futures testnet orders and was not run in this commit.
The existing simulation artifacts were regenerated:

- `testnet_fill_probe_simulation.csv`
- `testnet_fill_probe_simulation.jsonl`

## Verification

- `python -m py_compile order_manager.py tests\test_safety.py testnet_fill_probe.py config.py`
- `python -m pytest -q` -> `59 passed, 3 subtests passed`

No real testnet or live orders were sent in this follow-up.
