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
- Added `candle_correlation_overlay.py` as a backtest-only train-gated risk
  reducer prototype that never boosts size and only cuts setup buckets proven
  bad in the train slice.
- Added `trend_candle_entry_walk_forward.py`, which runs the same reducer as a
  true entry-time side-by-side walk-forward through `portfolio_backtest.py`.
- Added `strategy_decision_report.py` to consolidate the current Donchian,
  carry, trend/candle, PBO, and risk-adjusted evidence into a keep/kill report.
- Added `funding_predictability_report.py` as a research-only OOS funding
  persistence PoC. It learns thresholds on prior funding prints and validates
  only on future funding windows; it does not create an executor.
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
- Predictive-funding PoC scanned `42` liquid spot-backed USDT perpetuals and
  produced `0` strict passing symbols with a minimum `3` OOS-fold gate.
- Trend-quality attribution is diagnostic only; it is not wired as an active
  signal, filter, or risk gate.
- Candle-structure attribution is diagnostic only; it is not wired as an active
  signal, filter, or risk gate.
- The candle/correlation reducer learned `0` bad OOS-train buckets in the latest
  run, so it made no paper/testnet/live change and remains report-only.
- The true entry-time trend/candle walk-forward also learned `0` bad train
  buckets and reduced `0` trades, so there is still no activation case.
- `docs/STRATEGY_DECISION_2026_05_04.md` marks Donchian as `benchmark_only`;
  it is not an active live-money strategy.

## Validation

- Safety/unit test count after follow-up carry, trend-quality, candle-structure,
  and funding-predictability research pass: `133 passed, 3 subtests passed`.
- `python go_live_preflight.py --json` returns `go_live_blocked`, as expected.
  Current blockers include `TESTNET=True`, `LIVE_TRADING_APPROVED=False`,
  runtime-profile mismatch, `USER_DATA_STREAM_READY=False`, and safety flags
  that are intentionally off in the research profile.
- `python candle_correlation_overlay.py --trades portfolio_trades.csv --years 3`
  returned unchanged OOS results because no train-proven bad setup bucket met
  the reduction gate.
- `python trend_candle_entry_walk_forward.py --years 3` returned unchanged OOS
  metrics through the real entry-sizing backtest path: `106` OOS trades,
  `6002.34` PnL, PF `5.9885`, max DD `505.72`, and `0` reduced overlay trades.
- `python strategy_decision_report.py` returned verdict `benchmark_only` with
  `live_allowed=false` and `paper_change_allowed=false`.
- `python funding_predictability_report.py --auto-universe --days 180 ...`
  returned `42` scanned symbols, `203` fold rows, and `0` strict passing
  symbols. Short-history rows such as DOT/WLD were rejected as
  `insufficient_oos_folds`; longer-history rows such as AXL/BABY/ORCA failed
  consistent OOS predictive-edge requirements.
