# Stale Bar Guard 2026-05-01

Status: closed in code for the live/testnet bot loop. This does not approve live
trading.

## Closed Risk

The audit item was that after PC sleep, Windows session loss, network downtime,
or exchange data staleness, the bot could continue using `df.iloc[-2]` as if it
were the current last closed candle.

Changes:

- Added `BAR_AGE_GUARD_ENABLED = True`.
- Added `MAX_CLOSED_BAR_AGE_MULT = 1.25`.
- Added `execution_guard.closed_bar_age_decision(df, timeframe)`.
- `bot.py` now checks the last closed bar after indicator construction and
  before position management or new signal execution.

For `4h`, the default maximum closed-bar age is `5h`. For `2h`, it is `2.5h`.
This keeps normal hourly checks valid while blocking stale data after long
downtime.

## Verification

- `python -m py_compile bot.py config.py execution_guard.py tests\test_safety.py`
- `python -m pytest tests\test_safety.py -q` -> `66 passed, 3 subtests passed`

No real testnet or live orders were sent for this guard.

## Remaining Work

This guard prevents stale-bar execution. It does not replace the still-open
user-data stream/reconciliation decision, because exchange-side fills and stop
events can still happen between polling cycles.
