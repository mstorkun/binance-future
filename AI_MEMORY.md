# AI Memory / Project Handoff

Last updated: 2026-05-01

This file is the repo-local memory for future AI agents. Read it before making
strategy, risk, backtest, paper, testnet, or live-trading changes.

## User Priorities

- Speak Turkish with the user.
- Execute decisively when the user says "yap", but protect the working bot.
- Main strategy must not be changed casually.
- Profit must not be capped by artificial limits. Let strong trends run.
- Risk controls are welcome only if they improve robustness without reducing
  validated profitability.
- Live trading must stay blocked until paper/testnet/fill/monitoring gates pass.
- Do not treat any result as investment advice.

## Current Strategy

- Active portfolio candidate: `DOGE/USDT`, `LINK/USDT`, `TRX/USDT`.
- Previous active baseline was `SOL/USDT`, `ETH/USDT`, `BNB/USDT`; keep its
  results for comparison but do not assume it is still the current config.
- Primary timeframe: `4h`.
- Timeframe research exists in `docs/TIMEFRAME_SWEEP.md`: 2h scaled is a
  stronger candidate on return and worst walk-forward return, but 4h remains
  the active conservative default because drawdown/profit-factor are cleaner.
- Current profile: `growth_70_compound`.
- Leverage candidate: `10x`.
- Base risk: `4%` of current portfolio equity for the first open position,
  correlation-aware after that.
- Risk basis: `portfolio`, so sizing compounds with equity.
- Primary entry: Donchian breakout.
- Filters/context:
  - volume filter
  - ADX
  - RSI extreme filter
  - 1D EMA trend filter
  - weekly trend context calculated but not enforced
  - calendar/news risk
  - volume profile
  - candlestick/price-action context
  - Binance futures flow context
- Exits:
  - ATR initial stop
  - dynamic trailing stop
  - Donchian trend-exit
  - hard exchange-side fail-safe stop in live/testnet path

## Important Defaults

- `config.TESTNET = True`.
- `config.LIVE_TRADING_APPROVED = False`.
- `config.REQUIRE_ONE_WAY_MODE = True`.
- `config.MAX_OPEN_POSITIONS = 2`.
- `config.LIQUIDATION_GUARD_ENABLED = False`.
- `config.REQUIRE_WEEKLY_TREND_ALIGNMENT = False`.
- `config.WEEKLY_TREND_RISK_ENABLED = False`.
- `config.PROTECTIONS_ENABLED = False`.
- `config.EXIT_LADDER_ENABLED = False`.
- `config.PAIR_UNIVERSE_ENABLED = False`.
- `config.TWAP_ENABLED = False`.

The mature-bot add-ons are intentionally passive. Do not wire them into live or
paper order behavior until a side-by-side backtest/walk-forward/Monte Carlo
report proves they are net-positive.

## Latest Validated Results

Most recent validated active portfolio candidate:

- symbols: `DOGE/USDT`, `LINK/USDT`, `TRX/USDT`
- source command:
  `python portfolio_candidate_sweep.py --years 3 --min-size 3 --max-size 3 --top 30`
- confirmed command after config activation: `python portfolio_backtest.py`
- trades: `264`
- win rate: `83.33%`
- final equity: `11271.76 USDT`
- total return: `+1027.18% / 3 years`
- CAGR: `+124.21%/year`
- peak drawdown: `5.05%`
- profit factor: `10.1688`
- commission included: `1186.01`
- slippage included: `2223.78`
- funding included: `+166.62`

Other previous validation context:

- Previous `SOL/USDT,ETH/USDT,BNB/USDT` baseline:
  `244` trades, `81.97%` win rate, `5786.96` final equity, `79.54%` CAGR,
  `7.67%` peak DD, and rank `303` in the 455-combination 3-symbol sweep.
- Candidate portfolio walk-forward for `DOGE/USDT,LINK/USDT,TRX/USDT`:
  `7/7` fixed-profile windows positive, average test return `20.12%`, worst
  test return `5.25%`, worst peak DD `5.05%`, total test trades `155`.
- Candidate Monte Carlo for `DOGE/USDT,LINK/USDT,TRX/USDT`, profile
  `growth_70_compound`, `5000` iterations, block size `5`:
  block-bootstrap ending p05 `6191.14`, p50 `10685.20`, p95 `20594.79`,
  loss probability `0.00%`, peak-DD p95 `6.25%`, peak-DD max `11.77%`.
- Mature bot side-by-side compare:
  `python mature_bot_compare.py --years 3`
  showed baseline still best on CAGR. Current results:
  baseline `79.54%`, protections `76.89%`, exit_ladder `76.66%`,
  pair_universe `79.54%`, all_addons `74.06%`.
  Do not enable protections/exit ladder/all_addons with current parameters.
- Bias audit on SOL 1-year data passed:
  `python bias_audit.py --symbol SOL/USDT --years 1 --sample-step 96`
  returned `OK - no indicator drift detected`.
- Bias audit on active candidate symbols passed:
  `python bias_audit.py --symbol DOGE/USDT --years 1 --sample-step 96`,
  `python bias_audit.py --symbol LINK/USDT --years 1 --sample-step 96`, and
  `python bias_audit.py --symbol TRX/USDT --years 1 --sample-step 96` all
  returned `OK - no indicator drift detected`.
- Unit tests passed:
  `python -m pytest -q` -> `85` tests passed plus `3` subtests after the
  Claude follow-up fixes and tick precision audit. Covered areas include client
  order id duplicate classification, fetch-by-client-id behavior, partial-fill
  handling, trailing stop cleanup, hard-stop precision, reduce-only market
  amount normalization, stale closed-bar detection, trade decision snapshot
  persistence, emergency kill-switch dry-run/execute paths, live profile guard
  behavior, user-data stream live-gate behavior, and basic risk-adjusted metrics
  reporting plus correlation stress, pattern ablation, and exchange-filter cache
  TTL helpers, paper CSV append hardening, stale risk-code quarantine, and
  passive TWAP/executor guardrails, exact requirement pinning, and paper lock
  heartbeat refresh.
- Overfit-control report:
  `python risk_adjusted_report.py` now includes conservative proxies. Latest
  output: nominal Sharpe `3.6935`, `455` candidate sweep tests, Bonferroni alpha
  `0.00010989`, Sharpe haircut `5.9978`, deflated Sharpe proxy `-2.3043`, pass
  after haircut `false`, walk-forward `7/7` positive test folds but `7/7`
  severe train/test degradation folds and PBO proxy `1.0`. Treat this as
  strengthened no-go evidence, not live approval.
- Portfolio candidate sweep:
  `python portfolio_candidate_sweep.py --years 3 --min-size 3 --max-size 3 --top 30`
  ranked `DOGE/USDT,LINK/USDT,TRX/USDT` first with `264` trades, `83.33%`
  win rate, `11271.76` final equity, `124.21%` CAGR, `5.05%` peak DD, and
  `10.1688` profit factor. Current `SOL/USDT,ETH/USDT,BNB/USDT` ranked `303`
  with `79.54%` CAGR and `7.67%` peak DD. All top 30 rows included `TRX/USDT`,
  so this is a strong research lead but needs out-of-sample validation before
  any config change.
- Timeframe sweep:
  `python timeframe_sweep.py --years 3 --timeframes 1h 2h 4h --mc-iterations 2000 --block-size 5`
  and the same command with `--scaled-params`. Raw 1h produced extreme
  compounding (`3503.00%` CAGR) but is not fair evidence because indicator
  horizons shrink. Scaled results: 2h `161.27%` CAGR, `10.83%` peak DD, `7/7`
  WF positive, MC p05 ending `9472.13`; 4h `126.14%` CAGR, `5.05%` peak DD,
  `7/7` WF positive, MC p05 ending `6319.45`; 1h `113.64%` CAGR, `14.56%`
  peak DD, `6/7` WF positive. Do not switch to 1h. If switching to 2h, scale
  lookback parameters or add timeframe-aware parameters and restart paper.

## Recent Commits

- `28e5d43 Document candidate sweep results`
  - Added the first full 3-year candidate sweep evidence to repo notes.
- `7778a1b Add portfolio candidate sweep`
  - Added `portfolio_candidate_sweep.py`.
  - Added `docs/PORTFOLIO_CANDIDATE_SWEEP.md`.
  - Added a research-only symbol portfolio search flow.
- `785cbad Add passive mature bot operating layers`
  - Kept mature-bot add-ons passive.
  - Added side-by-side validation context.
- `4384b05 Add passive mature bot safeguards`
  - Added `protections.py`.
  - Added `exit_ladder.py`.
  - Added `bias_audit.py`.
  - Added `docs/MATURE_BOT_ADDONS.md`.
  - Added tests proving the new layers are neutral when disabled.
- `8250e93 Harden paper telemetry and execution safety`
  - Hardened paper runner and execution safety.
- `1259f8b Add paper telemetry runner`
- `62a522e Add futures flow and pattern risk context`

## Key Files

- `config.py`: all important safety, risk, fee, slippage, flow, and passive
  add-on toggles. Current values are `RUNTIME_PROFILE_NAME =
  "research_growth_70_compound"` and are research/paper/testnet only. Live mode
  is guarded by `LIVE_PROFILE` (`balanced_live_v1`: 5x, 3% risk, 3% daily loss,
  max 2 positions, cross margin) and `USER_DATA_STREAM_READY=False`.
- `data.py`: exchange factory and live profile guard. If `TESTNET=False`,
  `make_exchange()` requires both `LIVE_TRADING_APPROVED=True` and a runtime
  config that matches `config.LIVE_PROFILE`, plus a ready user-data stream gate.
- `strategy.py`: main signal and exit logic. Avoid changing this unless the user
  explicitly approves a strategy change and validation is rerun.
- `risk.py`: market, calendar, pattern, flow, and volume-profile risk
  multipliers.
- `risk_management.py`: deprecated quarantine marker. Its legacy
  `calculate_position_size()` now raises; use `risk.position_size()` and the
  portfolio risk path instead.
- `execution_guard.py`: wick/spike, hard-stop, mark-price stop, and orderbook
  guard logic. `hard_stop_from_soft()` must not round prices to fixed decimal
  places; exchange tick normalization belongs in `exchange_filters.py`. It also
  owns `closed_bar_age_decision()`, which blocks stale closed-bar processing
  after downtime.
- `account_safety.py`: shared account safety checks for one-way position mode
  per-symbol leverage confirmation, margin-mode confirmation, and hard-stop
  presence for open positions. `ops_status.py --exchange` can query this
  against Binance/testnet without changing the normal file-only status command.
- `order_manager.py`: live/testnet order placement, one-way mode check, hard
  stop placement, reduce-only close. It now attempts margin-mode confirmation
  before leverage and entry order submission. Signed order-management calls use
  `config.RECV_WINDOW_MS` via `signed_params()`. Entry, hard SL, trailing SL,
  close, and emergency close orders use deterministic `newClientOrderId`
  values; retry/timeout/duplicate paths reuse the same id and reconcile through
  Binance Futures `origClientOrderId` lookup. Duplicate detection must stay
  text-based; do not re-add broad `-2010`, `-2027`, or `-4015` duplicate
  classification. `_resolve_market_fill()` returns explicit requested, filled,
  and remaining quantities and applies `PARTIAL_FILL_POLICY` (`abort` default,
  `accept` optional) so state, SL, and rollback use filled size only. Trailing
  stop updates now fetch same-side reduce-only STOP orders and cancel extras
  after creating the new protected stop.
- `order_events.py`: append-only JSONL telemetry for live/testnet order
  lifecycle events. `order_manager.py` records entry, stop, close, emergency
  close, cancel, order ack/error, and fill-resolution events. Runtime output is
  `order_events.jsonl` and is ignored by git.
- `decision_snapshots.py`: append-only JSONL forensic snapshots for live/testnet
  entry decisions. `bot.py` writes entry candidates, risk blocks, successful
  opens, and failed opens to ignored `trade_decisions.jsonl`, including bar,
  indicator, flow, risk, and order-result context.
- `emergency_kill_switch.py`: dry-run-by-default emergency cancel/close CLI.
  Execution requires `--execute --yes-i-understand`; live config also requires
  `--allow-live`. It cancels open orders per symbol and closes positions with
  reduce-only market orders through the shared idempotent client-order-id path.
- `docs/API_KEY_SECURITY_RUNBOOK_2026_05_01.md`: Binance API key operations
  runbook. Live key scope is Reading + USD-M Futures trading only, no withdrawal
  or universal transfer, trusted static IPv4 only, separate testnet/live keys,
  monthly rotation, and narrow `-2015` triage.
- `docs/RISK_PROFILE_POLICY_2026_05_01.md`: documents that 10x/%4 is the active
  research profile, while `balanced_live_v1` is the only live profile shape that
  can pass the exchange factory guard.
- `docs/USER_DATA_STREAM_DECISION_2026_05_01.md`: documents the decision that
  REST polling is insufficient for live funds. Live exchange creation is blocked
  until a real testnet-proven USD-M Futures user-data stream implementation is
  ready.
- `docs/RISK_ADJUSTED_METRICS_2026_05_01.md`: documents basic Sharpe/Sortino/
  Calmar reporting and Bonferroni visibility for candidate sweeps. DSR/PBO or an
  equivalent conservative overfitting report remains future work.
- `docs/CORRELATION_STRESS_2026_05_01.md`: documents the report-only
  correlation stress pass. A covariance-aware cap still needs side-by-side
  validation before it can affect trading logic.
- `docs/PATTERN_ABLATION_2026_05_01.md`: documents the report-only
  pattern-risk ablation harness. Permutation/randomized-weight tests remain
  future work.
- `docs/EXCHANGE_FILTER_CACHE_2026_05_01.md`: documents the exchange filter
  cache TTL and manual refresh helper.
- `docs/PAPER_TELEMETRY_ATOMICITY_2026_05_01.md`: documents paper CSV telemetry
  flush/fsync hardening.
- `docs/STALE_RISK_CODE_QUARANTINE_2026_05_01.md`: documents the deprecated
  `risk_management.py` quarantine.
- `docs/PASSIVE_EXECUTION_GUARDRAILS_2026_05_01.md`: documents TWAP/executor
  passive-only guardrails and the remaining refactor gate.
- `docs/DEPENDENCY_PINNING_2026_05_01.md`: documents exact runtime/dev pins;
  `ccxt` is pinned to `4.5.51`.
- `docs/PAPER_LOCK_HEARTBEAT_2026_05_01.md`: documents the refreshed
  `PaperRunnerLock` heartbeat/mtime behavior.
- `docs/OVERFIT_CONTROLS_2026_05_01.md`: documents Bonferroni Sharpe haircut
  and walk-forward degradation/PBO proxies.
- `live_state.py`: persistent JSON state for live/testnet active positions.
  `bot.py` loads it at startup, writes after recovery/open/close/extreme/trailing
  changes, and reconciles stale local symbols against exchange open positions.
  Runtime output is `live_state.json` and is ignored by git.
- `alerts.py`: deterministic alert generation and append-only JSONL sink for
  local paper/testnet operations. `ops_status.py` attaches alerts to every
  status payload and `--emit-alerts` writes runtime output to ignored
  `alerts.jsonl`.
- `exchange_filters.py`: Binance Futures `exchangeInfo` filter validation for
  entry, stop, and reduce-only market close sizing. It validates tick size,
  step size, market lot size, minimum notional for entries/stops,
  percent-price bounds, and symbol trading status before testnet/live order
  submission. Cache entries expire after `EXCHANGE_FILTER_CACHE_TTL_SECONDS`;
  `refresh_symbol_filters()` forces a fresh fetch.
- `paper_runner.py`: no-order paper telemetry runner. `_append_csv()` creates
  parent directories and flushes/fsyncs paper CSV appends; schema-expanding
  rewrites use temp+replace.
- `paper_runtime.py`: tagged paper/shadow runtime isolation helpers for
  separate state/decision/equity/heartbeat files and temporary timeframe
  overrides.
- `portfolio_backtest.py`: current primary statistical backtest.
- `risk_metrics.py`: equity-path metrics and multiple-testing helpers. Provides
  annualized volatility, Sharpe, Sortino, Calmar, max drawdown, and Bonferroni
  alpha helpers.
- `risk_adjusted_report.py`: reads existing equity/sweep CSV outputs and writes
  ignored `risk_adjusted_report.json` with risk-adjusted metrics and
  multiple-testing summary.
- `correlation_stress.py`: report-only pairwise symbol return correlation
  stress. It writes ignored `correlation_stress_report.json` and
  `correlation_stress_pairs.csv`; it does not change sizing behavior.
- `pattern_ablation.py`: report-only pattern-risk on/off ablation. It writes
  ignored `pattern_ablation_results.csv`; it does not change default behavior.
- `portfolio_walk_forward.py`: portfolio walk-forward validation.
- `portfolio_monte_carlo.py`: trade-return Monte Carlo validation.
- `flow_data.py`: Binance public futures flow data with TTL/freshness handling.
- `protections.py`: passive mature-bot protections.
- `exit_ladder.py`: passive partial-TP/breakeven helper.
- `pair_universe.py`: passive dynamic pairlist scoring.
- `twap_execution.py`: passive TWAP slice planner. Marked `PASSIVE_ONLY`; it is
  not wired into order flow.
- `trade_executor.py`: passive lifecycle contract for future execution refactor.
  Marked `PASSIVE_ONLY`; it is not wired into order flow.
- `ops_status.py`: local paper/testnet status report.
- `paper_report.py`: detailed paper decision/equity/error report.
- `mature_bot_compare.py`: side-by-side add-on validation.
- `portfolio_candidate_sweep.py`: searches better symbol combinations without
  changing the strategy.
- `timeframe_sweep.py`: compares 1h/2h/4h with raw and scaled indicator
  horizons.
- `testnet_fill_probe.py`: locked testnet fill/slippage probe plus local
  simulation flags for partial-fill rollback and duplicate client-order-id
  reconciliation. It also has a real gated duplicate-client-order-id probe via
  `--probe-duplicate-client-order-id-real --approve-testnet-fill`; this sends
  real Binance Futures testnet orders and has not been run yet. Latest committed
  simulation artifacts are
  `testnet_fill_probe_simulation.csv` and `testnet_fill_probe_simulation.jsonl`;
  they do not send real exchange orders.
- `portfolio_param_walk_forward.py`: research-only portfolio walk-forward that
  selects Donchian/exit/volume/ATR-stop parameters and risk profile on the train
  window, then applies the selected candidate to the OOS test window. Use this
  to address the "fixed parameter walk-forward" methodology gap.
- `portfolio_cost_stress.py`: research-only replay of selected walk-forward OOS
  folds under harsher fee/slippage/funding assumptions. It keeps selected
  params fixed and writes `portfolio_cost_stress_results.csv` plus fold detail.
- `portfolio_holdout.py`: research-only final holdout check. It selects
  params/profile only on the pre-holdout train range, then evaluates the chosen
  candidate on the final holdout bars.
- Latest smoke:
  `python portfolio_param_walk_forward.py --years 3 --max-param-combos 6`
  completed in about 10 minutes, produced `7/7` positive OOS periods, average
  OOS return `80.04%`, worst OOS peak DD `14.88%`, and wrote
  `portfolio_param_walk_forward_results.csv`. Caveat: every fold selected
  `extreme_11pct`, so this is not live-approval evidence. The script now has
  `--risk-capped` for conservative/balanced/growth_70-only selection.
- Latest risk-capped smoke:
  `python portfolio_param_walk_forward.py --years 3 --max-param-combos 6 --risk-capped --out portfolio_param_walk_forward_risk_capped_results.csv`
  completed in about 5.5 minutes, produced `7/7` positive OOS periods, average
  OOS return `24.56%`, worst OOS peak DD `6.08%`, and selected
  `growth_70_compound` in all folds. This is more relevant than the uncapped
  smoke because `extreme_*` profiles are excluded.
- Latest cost stress:
  `python portfolio_cost_stress.py --wf-results portfolio_param_walk_forward_risk_capped_results.csv --years 3`
  produced baseline `7/7` positive OOS, 2x slippage `7/7`, 3x slippage `5/7`,
  fee+slippage 2x `5/7`, and severe costs `4/7`. Compounded OOS return stayed
  positive in every scenario, from `+345.36%` baseline to `+28.25%` severe, but
  severe stress is weak enough that live trading remains blocked.
- Latest holdout smoke:
  `python portfolio_holdout.py --years 3 --holdout-bars 500 --max-param-combos 6 --out portfolio_holdout_results.csv`
  selected `growth_70_compound|D15|DX8|VOL1.2|SL2.0` on the pre-holdout train
  range and produced final 500-bar holdout return `+10.55%`, win rate `70.00%`,
  30 trades, and peak DD `5.76%`. This supports continued paper/testnet
  observation, not live approval.
- `bias_audit.py`: lookahead/recursive indicator stability audit.
- `docs/MATURE_BOT_ADDONS.md`: activation rules for new add-ons.
- `docs/PORTFOLIO_CANDIDATE_SWEEP.md`: usage and latest smoke result for
  symbol portfolio search.
- `docs/AUDIT_DIFF_2026_05_01.md`: Claude 10-agent vs Codex triage merge. It
  now marks client order idempotency, partial-fill handling, trailing-stop
  orphan cleanup, tick precision, stale-bar guard, live decision snapshots, and
  emergency kill switch closed in code, API key runbook closed in docs, and risk
  profile mismatch closed with a live profile guard. User-data stream is closed
  as an architecture decision/live gate: polling is not accepted for live, and
  live exchange creation stays blocked until stream readiness is proven.

## Runtime / Worktree Notes

- A paper runner was restarted after the active DOGE/LINK/TRX symbol change and
  last observed healthy with PID `9400`, status `ok`, equity `1000`, wallet
  `1000`, open positions `0`, testnet `true`, and live trading approval
  `false`. This can go stale; verify `paper_heartbeat.json` before relying on
  it.
- A 2h scaled shadow paper runner was started with:
  `python paper_runner.py --loop --interval-minutes 60 --tag shadow_2h --timeframe 2h --scale-lookbacks`.
  Last observed PID `17316`, heartbeat `ok`, equity `1000`, wallet `1000`,
  open positions `0`, actions `{'no_signal': 6}`, warnings none. It writes
  isolated files such as `paper_shadow_2h_state.json` and can be checked with
  `python paper_report.py --tag shadow_2h`.
- Runtime paper files are ignored by git.
- Shadow paper mode is available:
  `python paper_runner.py --loop --interval-minutes 60 --tag shadow_2h --timeframe 2h --scale-lookbacks --reset`.
  Read it with `python paper_report.py --tag shadow_2h` or
  `python ops_status.py --tag shadow_2h --json`. Tagged files are isolated
  from the active 4h paper run.
- `walk_forward_results.csv` is a known pre-existing dirty file. Do not stage,
  revert, or rewrite it unless the user specifically asks.
- Large CSV files should not be read wholesale. Use `head`, `tail`,
  `Select-Object -First`, or script summaries.

## Safe Next Steps

1. Run `python portfolio_backtest.py` and unit tests after any active config
   change.
2. Monitor paper behavior with `python ops_status.py --json` and
   `python paper_report.py`; the latter shows latest per-symbol decisions,
   action counts, skips, flow freshness, risk multipliers, and runtime warnings.
3. Restart paper/testnet runners only after checking `ops_status.py --json`;
   already-running Python processes may still use the old imported config.
4. Tune `protections.py` and `exit_ladder.py` parameters only in backtest-only
   mode; current parameters reduce CAGR.
5. Add a real executor-backed paper implementation only after a net-positive
   side-by-side report.
6. Only after net-positive evidence and real fill review, consider live-trading
   gates.

## Do Not Do Without Explicit Approval

- Do not enable live trading.
- Do not disable `TESTNET`.
- Do not enable passive add-ons in live/paper flow without validation.
- Do not change the main signal to grid/DCA/martingale.
- Do not cap upside profits with fixed total-profit limits.
- Do not revert unrelated user or generated changes.
