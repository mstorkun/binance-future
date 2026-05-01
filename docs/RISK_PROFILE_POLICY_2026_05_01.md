# Risk Profile Policy 2026-05-01

Status: closes P0 #27 by separating the active research profile from the only
allowed live profile shape. This does not approve live trading.

## Active Runtime Profile

`config.py` currently runs:

- `RUNTIME_PROFILE_NAME = "research_growth_70_compound"`
- `TESTNET = True`
- `LIVE_TRADING_APPROVED = False`
- `LEVERAGE = 10`
- `RISK_PER_TRADE_PCT = 0.04`
- `DAILY_LOSS_LIMIT_PCT = 0.06`
- `MAX_OPEN_POSITIONS = 2`

This profile is research/paper/testnet only. It exists because the current
backtest and paper evidence was generated with that risk shape. It is not a
go-live profile.

## Required Live Profile Shape

`config.LIVE_PROFILE` defines the only allowed live profile:

- name: `balanced_live_v1`
- leverage: `5x`
- risk per trade: `3%`
- daily loss limit: `3%`
- max open positions: `2`
- margin mode: `cross`

If `config.TESTNET=False`, `data.make_exchange()` now checks the runtime config
against `LIVE_PROFILE`. A mismatch blocks live exchange creation even if
`LIVE_TRADING_APPROVED=True`.

## Why This Exists

The audit found that earlier docs discussed a balanced 5x/%3 profile while the
runtime config was the more aggressive 10x/%4 research profile. That mismatch
could make an operator believe the bot was running a safer profile than it
actually was.

The guard makes the mismatch fail closed.

## Required Checks

Before any future live attempt:

```bash
python ops_status.py --json
python ops_status.py --exchange --json
python emergency_kill_switch.py --json
python -m pytest -q
```

`ops_status.py --json` includes `live_profile`. It must show:

- `ok: true`
- `required_live_profile: balanced_live_v1`
- empty `mismatches`

The remaining P0 blockers still apply. Passing the profile guard alone is not
live approval.
