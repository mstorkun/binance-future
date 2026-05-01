# Trade Decision Snapshots 2026-05-01

Status: closed in code for entry decisions. This does not approve live trading.

## Closed Risk

The audit item was that after a live/testnet trade there was no forensic record
explaining why the bot opened or attempted to open the trade.

Changes:

- Added `decision_snapshots.py`.
- Added ignored runtime output `trade_decisions.jsonl`.
- `bot.py` now writes a snapshot for:
  - entry candidates that pass signal checks,
  - risk-blocked entry candidates,
  - successful opens,
  - failed opens.

Each row includes symbol, timeframe, signal, closed-bar timestamp, OHLCV,
indicator context, flow context when present, equity/free balance, risk basis,
open-position count, risk multiplier/reasons, intended price/ATR, and order
result fields such as size, entry, stops, and client order ids.

## Verification

- `python -m py_compile decision_snapshots.py bot.py config.py tests\test_safety.py`
- `python -m pytest -q` -> `67 passed, 3 subtests passed`

No real testnet or live orders were sent for this change.

## Runtime Note

`trade_decisions.jsonl` is intentionally ignored by git. If a future review
needs evidence, copy or summarize relevant rows into a dated doc rather than
committing the live runtime file directly.
