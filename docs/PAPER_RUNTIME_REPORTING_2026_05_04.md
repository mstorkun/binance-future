# Paper Runtime Reporting 2026-05-04

Status: paper/testnet observability improvement. This does not approve live
trading.

## What Changed

- `ops_status.py` now marks file-based runner state as `state_scope="paper"` and
  `compare_live_state_positions=False`.
- `alerts.py` only emits `state_position_mismatch` when a caller explicitly
  asks to compare paper/open-position state with `live_state`.
- `paper_report.py` now includes:
  - open position summaries from `PAPER_STATE_FILE`,
  - recent trade summary,
  - latest compact trade rows,
  - MFE/MAE fields when available.
- `paper_runner.py` records entry context and max favorable/adverse excursion
  fields for newly opened paper positions and closed-trade rows.
- `paper_decision_report.py` adds daily and weekly comparison windows for the
  default 4h paper run and the `shadow_2h` paper run.

## Why

The previous status payload compared paper positions with empty live state and
raised a misleading `state_position_mismatch` alert while live trading was
disabled. That alert is useful for real live/testnet exchange reconciliation,
but it is noise for local no-order paper tests.

The paper report also needed enough detail to answer:

- whether 4h or 2h is currently behaving better,
- whether a run is opening, skipping, holding, or closing,
- whether recent exits are profitable,
- whether an open trade has already seen meaningful favorable/adverse movement.

## Commands

```bash
python ops_status.py --json
python ops_status.py --tag shadow_2h --json
python paper_report.py
python paper_report.py --tag shadow_2h
python paper_decision_report.py
python paper_decision_report.py --json
```

## Current Observed State

Observed on 2026-05-04 before commit:

- default 4h paper runner: PID `9400`, status `ok`, equity `998.949551`, one
  open DOGE/USDT paper position, `alert_count=0`.
- `shadow_2h` paper runner: PID `17316`, status `ok`, equity `1008.757387`,
  no open positions, one closed paper trade.
- daily decision report:
  - default 4h: `72` decision rows, actions `no_signal=70`,
    `paper_open=1`, `skip=1`, `0` closed trades, `0` errors.
  - `shadow_2h`: `72` decision rows, actions `hold=1`, `no_signal=69`,
    `paper_open=1`, `skip=1`, `1` closed trade, total PnL `8.757387`,
    win rate `100%`, `0` errors.

These runtime numbers can drift as the paper runners continue.

## Caveats

- Active runner processes were not restarted. Newly added MFE/MAE tracking is
  applied by new code paths; already-open positions can show null excursion
  fields until the runner process is restarted or the position is reopened.
- The alert change is intentionally paper-scope only. Live/testnet exchange
  reconciliation should set `compare_live_state_positions=True` when that check
  is meaningful.

## Verification

- `python -m py_compile paper_runner.py paper_report.py paper_decision_report.py ops_status.py alerts.py tests\test_safety.py`
- `python -m pytest -q` -> `100 passed, 3 subtests passed`
