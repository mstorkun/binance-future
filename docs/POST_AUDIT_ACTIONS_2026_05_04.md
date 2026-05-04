# Post-Audit Actions - 2026-05-04

This note records the concrete actions taken after the Claude 12-agent audit and
the Codex multi-agent synthesis. It is a working implementation log, not live
approval.

## Decision

- Keep live trading blocked.
- Freeze the current Donchian breakout system as a benchmark/research line, not
  as the main live-money strategy.
- Open a new research lane for funding-rate carry / delta-neutral strategies.
- Prioritize production safety fixes that reduce account-damage risk without
  changing the current paper signal semantics.

## Implemented

- Added `runtime_guards.py` with a persistent `trading_disabled.flag`.
- Updated `emergency_kill_switch.py` so execute mode writes the trading-disabled
  flag after emergency cancel/close actions.
- Updated `data.make_exchange()` so live exchange creation fails when the
  trading-disabled flag exists.
- Extended `LIVE_PROFILE` so live mode also requires
  `LIQUIDATION_GUARD_ENABLED=True` and `PROTECTIONS_ENABLED=True`.
- Added `go_live_preflight.py`, a fail-closed preflight report for live mode.
- Hardened `live_state.py` with fsync-backed writes, backup rotation, backup
  recovery, and fail-closed corruption handling.
- Changed `order_manager.close_position_market()` so existing protection orders
  are retained until a reduce-only close is confirmed fully filled.
- Updated `bot.py` so failed or partial closes keep local state instead of
  popping the position optimistically.
- Added same-bar guards in `execution_guard.py`, `paper_runner.py`, and `bot.py`
  so a position opened from a closed bar is not immediately managed or reopened
  from that same bar.
- Added `carry_research.py` as a research-only funding-rate carry scanner.
- Extended `carry_research.py` with prior-signal dynamic entry/exit threshold
  backtests and threshold-grid optimization.
- Added `trend_quality_report.py` as report-only attribution for long/short
  trade performance by trend-quality context.
- Added `candle_structure.py` and `candle_structure_report.py` as report-only
  attribution for candle body/range, density/compression, persistence, and
  correlation context.
- Updated `config.example.py` to keep API-key examples env-only.

## Still Blocked

- User-data stream is not testnet-proven and not wired as live authority.
- `USER_DATA_STREAM_READY=False`.
- `LIVE_TRADING_APPROVED=False`.
- Active runtime profile remains research-only and does not match
  `balanced_live_v1`.
- `priceProtect` still needs an empirical Binance Futures testnet probe before
  changing behavior.
- Funding carry is only a research scanner; no spot/perp delta-neutral executor
  exists yet.
- Static and dynamic-threshold carry scans both produced `0` passing candidates
  under current cost and `6%` USDT benchmark assumptions.
- Trend-quality attribution is diagnostic only; it is not wired as an active
  signal, filter, or risk gate.
- Candle-structure attribution is diagnostic only; it is not wired as an active
  signal, filter, or risk gate.

## Validation

- Safety/unit test count after follow-up carry, trend-quality, and candle-structure research pass: `123 passed, 3 subtests passed` for
  both `tests/test_safety.py` and the full `python -m pytest -q` suite.
- `python go_live_preflight.py --json` returns `go_live_blocked`, as expected.
  Current blockers include `TESTNET=True`, `LIVE_TRADING_APPROVED=False`,
  runtime-profile mismatch, `USER_DATA_STREAM_READY=False`, and safety flags
  that are intentionally off in the research profile.
