# Exchange Filter Cache 2026-05-01

Status: closes the P1 cache-refresh gap for Binance exchange filters.

## Why

`exchange_filters.py` cached symbol filters forever. If Binance changed tick
size, lot size, market lot size, min notional, or percent-price bounds while the
bot kept running, order validation could use stale constraints.

## Changes

- Added `config.EXCHANGE_FILTER_CACHE_TTL_SECONDS = 3600`.
- `exchange_filters.get_symbol_filters()` now refreshes stale cache entries.
- Added `exchange_filters.refresh_symbol_filters()` for explicit startup or
  recovery refresh.
- Added unit coverage for cache reuse, manual refresh, and TTL expiry behavior.

## Runtime Behavior

- Default TTL is 1 hour.
- Set TTL to `0` to force a fetch on every call.
- `clear_cache()` still clears all cached filters.

## Verification

- `python -m py_compile exchange_filters.py config.py tests\test_safety.py`
- `python -m pytest -q` -> `78 passed, 3 subtests passed`
