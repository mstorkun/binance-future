# Tick Precision Audit 2026-05-01

Status: closed in code for current live/testnet order paths. This does not
approve live trading.

## Closed Risk

The audit item was that fixed decimal rounding could make DOGE/TRX-style prices
or quantities invalid or materially wrong.

Changes:

- `execution_guard.hard_stop_from_soft()` no longer rounds hard stops to two
  decimals. It returns the raw ATR-adjusted stop.
- `_create_sl_order()` continues to route hard SL and trailing SL prices through
  `exchange_filters.validate_stop_order()`, which normalizes stop prices to the
  Binance `tickSize` in the protective direction.
- `exchange_filters.normalize_market_amount()` now normalizes reduce-only
  market close quantity to `MARKET_LOT_SIZE` / `LOT_SIZE`.
- `order_manager.close_position_market()` and emergency rollback close now use
  that market-lot normalization before submitting reduce-only market orders.

## Covered Paths

| Path | Price Precision | Amount Precision |
|---|---|---|
| Entry market | No order price | `validate_entry_order()` market-lot floor |
| Hard SL | `validate_stop_order()` tick normalization | `validate_stop_order()` lot floor |
| Trailing SL | `validate_stop_order()` tick normalization | `validate_stop_order()` lot floor |
| Trend close | No order price | `normalize_market_amount()` market-lot floor |
| Emergency rollback close | No order price | `normalize_market_amount()` market-lot floor |

## Verification

- `python -m py_compile exchange_filters.py execution_guard.py order_manager.py tests\test_safety.py testnet_fill_probe.py`
- `python -m pytest -q` -> `63 passed, 3 subtests passed`
- `python testnet_fill_probe.py --simulate-partial-fill --simulate-duplicate-client-order-id --simulation-out testnet_fill_probe_simulation.csv`

No real testnet or live orders were sent for this audit.

## Remaining Exchange Evidence

Real testnet order probes are still useful for empirical behavior, especially:

- duplicate `newClientOrderId` behavior,
- real stop-order response fields,
- partial fill reporting fields.

Those are not prerequisites for this code-level tick precision closure, but
they remain part of the broader live no-go checklist.
