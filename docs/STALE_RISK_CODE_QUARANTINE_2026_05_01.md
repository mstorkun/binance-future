# Stale Risk Code Quarantine 2026-05-01

Status: closes the P1 `risk_management.py` stale-code item.

## Why

`risk_management.py` contained a legacy margin-times-leverage sizing formula.
The active bot uses ATR-stop sizing through `risk.py` and portfolio sizing
through `portfolio_backtest.py` / `order_manager.py`. Keeping the old helper
callable made it too easy to accidentally reintroduce incompatible sizing.

## Change

`risk_management.calculate_position_size()` now raises a clear RuntimeError and
points callers to `risk.position_size()` and the current portfolio risk path.

The file remains in the repo as a quarantine marker so old imports fail loudly.

## Verification

- `python -m py_compile risk_management.py tests\test_safety.py`
- `python -m pytest tests\test_safety.py -q` -> `80 passed, 3 subtests passed`
- `python -m pytest -q` -> `80 passed, 3 subtests passed`
