# Paper Telemetry Atomicity 2026-05-01

Status: closes the P1 paper CSV append hardening item.

## Why

Paper telemetry CSV files are runtime evidence. If the process or OS stops
during a write, buffered rows can be lost or partially written.

## Changes

- `paper_runner._append_csv()` now flushes and `fsync`s after each append or
  schema-expanding rewrite.
- `_append_csv()` creates parent directories before writing.
- Existing schema-expanding writes still use a temporary file plus `os.replace`.
- Added unit coverage for nested output path creation.

## Scope

This hardens paper CSV telemetry only:

- `paper_decisions.csv`
- `paper_trades.csv`
- `paper_equity.csv`
- `paper_errors.csv`

JSONL sinks such as `order_events.jsonl`, `alerts.jsonl`, and
`trade_decisions.jsonl` already flush and fsync their writes.

## Verification

- `python -m py_compile paper_runner.py tests\test_safety.py`
- `python -m pytest -q` -> `79 passed, 3 subtests passed`
