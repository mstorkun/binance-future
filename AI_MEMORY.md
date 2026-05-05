# AI Memory / Project Handoff

Last updated: 2026-05-04

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
- After the 2026-05-04 12-agent audit, treat Donchian breakout as a benchmark
  strategy until stronger out-of-sample evidence appears. Funding-rate carry /
  delta-neutral research has scanner and predictive-PoC coverage now, but no
  executor-ready edge has passed strict OOS gates. Cross-exchange basis has
  also been checked as a PoC and remains non-executor-ready.

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
- `config.TRADING_DISABLED_FLAG = "trading_disabled.flag"`.
- `config.LIVE_STATE_FAIL_CLOSED = True`.

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
  `python -m pytest -q` -> `136` tests passed plus `3` subtests after
  post-audit safety, funding-predictability, and cross-exchange additions.
  Covered areas include client order id duplicate classification,
  fetch-by-client-id behavior, partial-fill handling, trailing stop cleanup,
  hard-stop precision, reduce-only market
  amount normalization, stale closed-bar detection, trade decision snapshot
  persistence, emergency kill-switch dry-run/execute paths, live profile guard
  behavior, user-data stream live-gate behavior, and basic risk-adjusted metrics
  reporting plus correlation stress, pattern ablation, and exchange-filter cache
  TTL helpers, paper CSV append hardening, stale risk-code quarantine, and
  passive TWAP/executor guardrails, exact requirement pinning, and paper lock
  heartbeat refresh, bias-audit report serialization, PBO matrix reporting,
  paper/live alert scoping, paper report open-position/trade summaries,
  4h-vs-2h paper decision reporting, and Binance user-stream order-update
  parsing, listenKey lifecycle helpers, conservative user-stream reconciliation
  decisions, the user-stream runtime handler, the websocket runner duplicate
  and out-of-order gate, live-state backup recovery/fail-closed handling,
  trading-disabled flag behavior, live preflight blocking, partial close
  protection retention, funding-carry summary math, and same-bar paper/live
  entry management guards, plus dynamic-threshold carry entry/exit tests that
  verify prior-signal use, invalid threshold rejection, optimizer selection, and
  trend-quality report bucketing, plus candle-structure feature/report tests.
- 2026-05-04 12-agent audit response:
  `docs/POST_AUDIT_ACTIONS_2026_05_04.md` records the applied Codex response.
  The Donchian `growth_70_compound` evidence remains useful for benchmarking,
  but not live approval. Funding-rate carry / delta-neutral is the next research
  lane via `carry_research.py`; no carry executor exists yet.
- First broad carry scan:
  `python carry_research.py --auto-universe --days 180 --min-quote-volume-usdt 50000000 --max-symbols 80 --out carry_candidates.csv --universe-out carry_universe.csv --json`
  scanned `32` active ASCII spot-backed USDT perpetuals. Passing candidates:
  `0`. Best row was `TST/USDT:USDT` with `3.7441%` annualized net after
  entry/exit cost and `-2.2559%` net APR versus a `6%` USDT benchmark. See
  `docs/CARRY_RESEARCH_2026_05_04.md`.
- Dynamic-threshold carry scan:
  `python carry_research.py --auto-universe --days 180 --min-quote-volume-usdt 50000000 --max-symbols 80 --dynamic-enter-grid 0.00005 0.000075 0.0001 0.00015 --dynamic-exit-grid 0 0.00002 0.00005 --dynamic-signal-window 3 --out carry_candidates.csv --universe-out carry_universe.csv --json`
  scanned `33` active ASCII spot-backed USDT perpetuals in the latest live
  market list. Passing candidates: `0`; single dynamic-threshold passing
  candidates: `0`; best grid-optimized passing candidates: `0`. Best active
  grid row was `PARTI/USDT:USDT` with enter `0.000075`, exit `0.00005`, `1`
  entry, `13` active funding periods, `-0.3764%` net after cost, and `-0.4477%`
  versus the prorated `6%` USDT benchmark. Do not build a live carry executor
  from the simple Binance spot/perp carry model.
- Funding predictability PoC:
  `python funding_predictability_report.py --auto-universe --days 180 --min-quote-volume-usdt 50000000 --max-symbols 80 --signal-window 3 --horizon 3 --top-quantile 0.8 --train-samples 360 --test-samples 90 --roll-samples 90 --min-selected 10 --min-folds 3 --out funding_predictability_results.csv --folds-out funding_predictability_folds.csv --universe-out funding_predictability_universe.csv --json-out funding_predictability_report.json --md-out docs/FUNDING_PREDICTABILITY_2026_05_04.md`
  scanned `42` liquid spot-backed USDT perpetuals and wrote
  `docs/FUNDING_PREDICTABILITY_2026_05_04.md`. Strict pass count: `0`. Top
  short-history apparent edges such as DOT/WLD were rejected as
  `insufficient_oos_folds`; longer-history rows such as AXL/BABY/ORCA failed
  consistent OOS predictive-edge requirements. Do not build a funding executor
  from this PoC.
- Cross-exchange basis PoC:
  `python cross_exchange_basis_report.py --exchanges binance okx bybit --days 180 --min-quote-volume-usdt 50000000 --max-symbols 60 --train-samples 45 --test-samples 15 --roll-samples 15 --min-folds 3 --min-test-samples 10 --earn-apr 6 --out cross_exchange_basis_results.csv --folds-out cross_exchange_basis_folds.csv --universe-out cross_exchange_basis_universe.csv --json-out cross_exchange_basis_report.json --md-out docs/CROSS_EXCHANGE_BASIS_2026_05_04.md`
  scanned common Binance/OKX/Bybit USDT perpetuals and wrote
  `docs/CROSS_EXCHANGE_BASIS_2026_05_04.md`. Result: `49` universe symbols,
  `147` exchange-pair rows, `57` rows with OOS folds, `171` fold rows, and
  strict pass count `0`. Best fold-producing row was DOT Binance/OKX with
  gross spread `0.2966%`, but after modeled cost and USDT benchmark it was
  `-1.6095%` net versus benchmark. Do not build a cross-exchange basis executor
  from this PoC.
- Trend-quality attribution:
  `python trend_quality_report.py --trades portfolio_trades.csv --json-out trend_quality_report.json --md-out docs/TREND_QUALITY_REPORT_2026_05_04.md --min-token-trades 10`
  is report-only and does not change bot behavior. Latest active portfolio
  trade set: `264` trades, total PnL `10271.77`, win rate `83.3333%`, profit
  factor `10.1688`. Quality buckets: high `104` trades / `5807.53` PnL /
  `1.2776%` mean return, medium `92` trades / `2700.63` PnL / `0.8366%` mean
  return, low `68` trades / `1763.61` PnL / `0.5825%` mean return. Short trades
  contributed `6597.06` PnL vs long `3674.71`, but `market:trend` context still
  improved mean return (`1.2893%` vs overall `0.9449%`). This supports measuring
  trend quality before changing filters; it is not enough by itself to activate
  a stricter live/paper filter.
- Candle-structure attribution:
  `python candle_structure_report.py --trades portfolio_trades.csv --years 3 --json-out candle_structure_report.json --md-out docs/CANDLE_STRUCTURE_REPORT_2026_05_04.md`
  is report-only and does not change bot behavior. It scores closed-candle body
  length, wick rejection, density/compression breakout, directional persistence,
  range-volume correlation, and symbol return correlation. Latest active
  portfolio trade set: aligned candle-structure bias `75` trades / `5048.18`
  PnL / `1.4387%` mean return; neutral `88` trades / `2772.76` PnL / `0.9020%`
  mean return; contra `101` trades / `2450.83` PnL / `0.6156%` mean return.
  Symbol max absolute return correlations: DOGE/LINK `0.7017`, TRX max
  `0.4067`. This suggests candle structure may be useful as an adaptive sizing
  overlay, not as a hard filter, and needs side-by-side WF/cost-stress proof
  before activation.
- Candle/correlation train-gated reducer:
  `python candle_correlation_overlay.py --trades portfolio_trades.csv --years 3`
  is backtest-only and does not change bot, paper, testnet, or live behavior.
  It never boosts size. It only reduces setup buckets that were negative in
  train and had profit factor below `1.0`, using closed-bar dynamic correlation
  and trend-quality buckets. Latest OOS result: `104` OOS trades, `0` learned
  bad train buckets, `0` reduced OOS trades, baseline and reducer both
  `6415.09` OOS PnL with max DD `516.26`. Do not activate it until a true
  entry-time sizing backtest/walk-forward proves improvement.
- Trend/candle entry-time walk-forward:
  `python trend_candle_entry_walk_forward.py --years 3` runs the reducer through
  the real `portfolio_backtest.py` entry sizing hook rather than post-hoc trade
  scaling. It is research-only and does not change paper/testnet/live behavior.
  Latest OOS result: baseline `106` OOS trades / `6002.34` PnL / PF `5.9885` /
  max DD `505.72`; entry-time reducer learned `0` bad train buckets, reduced
  `0` overlay trades, and returned identical OOS metrics. This provides no
  activation case for trend/candle risk reduction.
- Strategy decision:
  `python strategy_decision_report.py` writes
  `docs/STRATEGY_DECISION_2026_05_04.md`. Current verdict is
  `benchmark_only`: keep Donchian as a benchmark/research line, keep live
  blocked, do not activate trend/candle/correlation reducers in paper/testnet,
  and do not build a funding or cross-exchange basis executor from the current
  PoCs.
  Positive evidence remains useful for benchmarking, but the deflated-Sharpe
  proxy is negative, train/test degradation is severe, simple carry has `0`
  passing candidates, predictive funding has `0` strict passing symbols,
  cross-exchange basis has `0` passing pairs, and true entry-time trend/candle
  WF found no activation case.
- Overfit-control report:
  `python risk_adjusted_report.py` now includes conservative proxies. Latest
  output: nominal Sharpe `3.6935`, `455` candidate sweep tests, Bonferroni alpha
  `0.00010989`, Sharpe haircut `5.9978`, deflated Sharpe proxy `-2.3043`, pass
  after haircut `false`, walk-forward `7/7` positive test folds but `7/7`
  severe train/test degradation folds and PBO proxy `1.0`. Treat this as
  strengthened no-go evidence, not live approval.
- Bias-audit artifact:
  `python bias_audit_report.py --symbols DOGE/USDT LINK/USDT TRX/USDT --years 1 --sample-step 96 --fail-on-issue`
  wrote `docs/BIAS_AUDIT_REPORT_2026_05_01.json`; DOGE/LINK/TRX each used
  `2190` 4h rows and reported `0` issues.
- Executor decision:
  `trade_executor.py` and `twap_execution.py` remain quarantined research-only
  helpers. Do not wire them into paper/testnet/live until user-data stream,
  fill reconciliation, persistence, and A/B evidence exist.
- PBO harness:
  `portfolio_param_walk_forward.py --matrix-out portfolio_param_candidate_matrix.csv`
  can now write the full candidate-by-fold matrix, and `pbo_report.py` reports
  selected candidate OOS rank/PBO from that matrix.
- High-return futures research pivot (user directive, 2026-05-04):
  user explicitly wants to continue toward a Binance Futures bot targeting at
  least `80%` net annual return with dynamic long/short/wait and dynamic risk,
  accepting that losses are possible. Do not redirect this thread to GSM or
  passive yield. Keep live trading blocked until evidence passes costs,
  walk-forward, drawdown, and fill-quality gates.
- New research-only alpha-path modules from the pivot:
  `liquidation_hunting_report.py` tests an OHLCV liquidation proxy with
  cooldown/per-day trade caps and a minimum OOS sample-days gate. Latest DOGE
  15m 45d smoke had `0` passing rows because OOS sample was only `17.9896`
  days despite high annualized short-sample math.
  `adaptive_decision_report.py` trains a small ridge model over indicators,
  candle features, multi-timeframe context, BTC/ETH market context, BTC leader
  features, and modeled costs; it chooses long/short/wait and dynamic risk.
  Latest DOGE 15m 60d smoke with MTF candle gate produced `44` OOS trades,
  `-13.4415%` return, `-88.8784%` CAGR, `38.0447%` max DD, PF `0.8598`,
  and failed `target_not_met|drawdown_limit|profit_factor_low`.
- New context/gating modules:
  `macro_event_policy.py` maps official macro/crypto event categories into
  calendar-risk rows; `news_direction_policy.py` only allows directional news
  trading from trusted sources with market-reaction confirmation;
  `btc_market_leader.py` adds BTC trend/shock/correlation/beta context for alt
  decisions; `multi_timeframe_candle.py` creates weekly/daily/4h/1h/trigger
  candle features and a gate that blocks naked minute triggers, weekly/daily
  conflict, HTF compression, outside-mid indecision, and late daily expansion.
  These are research-only and are not wired into live execution.
- Urgent exit policy:
  `urgent_exit_policy.py` implements the user's exit preference: do not churn
  on small adverse moves; let the bot hold losing long/short positions when
  market/trend/news/indicator context still supports the thesis; allow around
  `30%` adverse account-level loss only with supportive context and force
  exit if that context is absent; force
  `reduceOnly` market close at the absolute `50%` adverse cap, when thesis is
  invalid near the large-loss zone, or when liquidation buffer gets too tight.
  It is wired into `bot.py`, `paper_runner.py`, and passive `trade_executor.py`;
  live trading remains blocked by preflight. `execution_guard.stop_decision()`
  now prioritizes hard stop over soft stop when both are touched, so the soft
  stop hold policy cannot shadow the exchange fail-safe level.
- Current high-return research docs:
  `docs/CANDLE_ORDERFLOW_RESEARCH_2026_05_04.md`,
  `docs/LIQUIDATION_HUNTING_2026_05_04.md`,
  `docs/MACRO_NEWS_RISK_POLICY_2026_05_04.md`,
  `docs/NEWS_DIRECTION_STRATEGY_PLAN_2026_05_04.md`,
  `docs/BTC_MARKET_LEADER_OVERLAY_2026_05_04.md`,
  `docs/MULTI_TIMEFRAME_CANDLE_STRATEGY_2026_05_04.md`, and
  `docs/ADAPTIVE_DECISION_MODEL_2026_05_04.md`,
  `docs/URGENT_EXIT_POLICY_2026_05_04.md`.
- Full PBO result:
  On 2026-05-02,
  `python portfolio_param_walk_forward.py --years 3 --train-bars 3000 --test-bars 500 --roll-bars 500 --risk-capped --out pbo_full_wf.csv --matrix-out portfolio_param_candidate_matrix.csv`
  took about 61.5 minutes. `python pbo_report.py --matrix portfolio_param_candidate_matrix.csv --out pbo_report.json`
  produced PBO `0.1429`, average OOS rank percentile `0.8764`, median OOS rank
  percentile `0.9860`, selected candidates OOS top-half in `6/7` folds, and
  positive selected test folds `7/7`. Artifacts are committed under
  `docs/PBO_FULL_RESULT_2026_05_02.md`, `docs/PBO_FULL_REPORT_2026_05_02.json`,
  `docs/PBO_SELECTED_WF_2026_05_02.csv`, and
  `docs/PBO_CANDIDATE_MATRIX_2026_05_02.csv`.
- User-stream parser:
  `user_stream_events.py` parses Binance USD-M Futures `ORDER_TRADE_UPDATE`
  events, records them through `order_events.record()`, and flags terminal,
  partial, liquidation/ADL, and immediate-reconcile events.
- User-stream listenKey helper:
  `user_stream_client.py` adds start/keepalive helpers, private websocket URL
  construction, and `ListenKeyState` keepalive/reconnect timing.
- User-stream reconcile:
  `user_stream_reconcile.py` applies parsed order updates to local positions
  conservatively. It removes state on reduce-only filled stops or
  liquidation/ADL, and marks partial/non-terminal updates.
- User-stream runtime handler:
  `user_stream_runtime.py` records one parsed update, applies reconcile
  decisions, persists changed `live_state` positions, and records a
  `user_stream_reconcile_decision`.
- User-stream runner:
  `user_stream_runner.py` adds the first websocket consumer skeleton with
  duplicate and out-of-order gating, listenKey keepalive/reconnect timing,
  connection-error telemetry, and routing into `user_stream_runtime.py`. It is
  not testnet-proven, not wired into `bot.py`, and does not change
  `USER_DATA_STREAM_READY=False`.
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
  It also blocks live exchange creation when `trading_disabled.flag` exists.
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
  after downtime, and `same_closed_bar_as_entry()`, which prevents evaluating an
  entry bar as if the position existed during that bar.
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
  after creating the new protected stop. Market close now retains existing
  protection orders until the reduce-only close is confirmed fully filled.
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
  Execute mode also writes `trading_disabled.flag`, so future entries stay
  blocked until the flag is explicitly cleared.
- `runtime_guards.py`: persistent trading-disabled flag helpers. Live exchange
  creation and `bot.py` new-entry logic respect this flag.
- `go_live_preflight.py`: fail-closed live readiness report. It checks testnet
  status, live approval, live profile match, user-data stream readiness, safety
  flags, trading-disabled flag state, and required runbooks.
- `carry_research.py`: research-only funding-rate carry scanner. It can scan a
  manual symbol list or discover a liquid spot-backed USDT perpetual universe
  with `--auto-universe`. It compares annualized funding against an earn-style
  benchmark after conservative paired entry/exit costs and reports simple
  carry-backtest metrics.
- `trend_quality_report.py`: report-only trade attribution from
  `portfolio_trades.csv`. It parses `risk_reasons`, scores trend-quality
  context, and writes markdown/JSON summaries. It must not be treated as an
  active trading filter without side-by-side backtest, walk-forward, and cost
  stress evidence.
- `candle_structure.py`: report-only closed-candle body/range/wick,
  density/compression, directional-persistence, return-autocorrelation, and
  volume-range-correlation features. It emits side-specific candle-structure
  bias/confidence but is not wired into strategy/risk.
- `candle_structure_report.py`: fetches historical data, annotates
  `portfolio_trades.csv` with the prior signal bar's candle-structure features,
  adds per-symbol max absolute return correlation, and writes
  `docs/CANDLE_STRUCTURE_REPORT_2026_05_04.md` plus ignored JSON.
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
- `docs/BIAS_AUDIT_REPORT_2026_05_01.md` and `.json`: committed reproducible
  lookahead/recursive drift audit result for DOGE/LINK/TRX.
- `docs/EXECUTOR_REFACTOR_DECISION_2026_05_01.md`: records the decision to keep
  passive executor/TWAP helpers quarantined.
- `docs/PBO_MATRIX_HARNESS_2026_05_01.md`: documents the candidate-by-fold
  matrix and `pbo_report.py` workflow.
- `docs/PBO_FULL_RESULT_2026_05_02.md`: documents the first full PBO matrix
  result and links committed JSON/CSV artifacts.
- `docs/USER_STREAM_EVENT_PARSER_2026_05_01.md`: documents the parser-only
  first layer for Binance user data stream events.
- `docs/USER_STREAM_LISTEN_KEY_2026_05_01.md`: documents listenKey lifecycle
  helpers for the future user-data stream runner.
- `docs/USER_STREAM_RECONCILE_2026_05_01.md`: documents conservative
  local-position decisions from parsed user-stream events.
- `docs/USER_STREAM_RUNTIME_HANDLER_2026_05_01.md`: documents the single-message
  parser/reconcile/live_state adapter for future websocket consumption.
- `docs/USER_STREAM_RUNNER_2026_05_04.md`: documents the websocket consumer
  skeleton, duplicate/out-of-order gate, keepalive/reconnect timing, and the
  remaining testnet-proof work before stream readiness can be marked true.
- `docs/PAPER_RUNTIME_REPORTING_2026_05_04.md`: documents paper/live alert
  scoping, enriched paper report output, and the 4h-vs-2h daily/weekly decision
  report.
- `live_state.py`: persistent JSON state for live/testnet active positions.
  `bot.py` loads it at startup, writes after recovery/open/close/extreme/trailing
  changes, and reconciles stale local symbols against exchange open positions.
  Runtime output is `live_state.json` and is ignored by git.
- `alerts.py`: deterministic alert generation and append-only JSONL sink for
  local paper/testnet operations. `ops_status.py` attaches alerts to every
  status payload and `--emit-alerts` writes runtime output to ignored
  `alerts.jsonl`. `state_position_mismatch` is only emitted when
  `compare_live_state_positions=True`, so paper-only state no longer creates a
  false live-state mismatch alert.
- `exchange_filters.py`: Binance Futures `exchangeInfo` filter validation for
  entry, stop, and reduce-only market close sizing. It validates tick size,
  step size, market lot size, minimum notional for entries/stops,
  percent-price bounds, and symbol trading status before testnet/live order
  submission. Cache entries expire after `EXCHANGE_FILTER_CACHE_TTL_SECONDS`;
  `refresh_symbol_filters()` forces a fresh fetch.
- `paper_runner.py`: no-order paper telemetry runner. `_append_csv()` creates
  parent directories and flushes/fsyncs paper CSV appends; schema-expanding
  rewrites use temp+replace. New paper positions and closed-trade rows include
  entry context and MFE/MAE fields. It skips management on the same closed bar
  used for entry and blocks same-bar re-entry after a close.
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
- `pbo_report.py`: reads a candidate-by-fold matrix and reports selected
  candidate OOS rank/PBO-style diagnostics.
- `user_stream_events.py`: parser/telemetry adapter for Binance
  `ORDER_TRADE_UPDATE` events.
- `user_stream_client.py`: listenKey lifecycle and websocket URL helpers.
- `user_stream_reconcile.py`: conservative position-state decisions from parsed
  user-stream order updates.
- `user_stream_runtime.py`: single-message handler that records, reconciles, and
  persists parsed user-stream order updates.
- `user_stream_runner.py`: websocket consumer skeleton for Binance USD-M
  Futures user-data streams. It has duplicate/out-of-order guards, keepalive and
  reconnect timing, and routes order updates into `user_stream_runtime.py`; it
  is still not testnet-proven and not a live-readiness gate.
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
- `paper_report.py`: detailed paper decision/equity/error/open-position/trade
  report.
- `paper_decision_report.py`: daily/weekly comparison report for default 4h and
  tagged shadow paper runs such as `shadow_2h`.
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
  to address the "fixed parameter walk-forward" methodology gap. It also accepts
  `--matrix-out` for the full candidate-by-fold PBO matrix.
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
- `bias_audit_report.py`: multi-symbol bias-audit JSON artifact writer.
- `docs/MATURE_BOT_ADDONS.md`: activation rules for new add-ons.
- `docs/PORTFOLIO_CANDIDATE_SWEEP.md`: usage and latest smoke result for
  symbol portfolio search.
- `docs/AUDIT_DIFF_2026_05_01.md`: Claude 10-agent vs Codex triage merge. It
  now marks client order idempotency, partial-fill handling, trailing-stop
  orphan cleanup, tick precision, stale-bar guard, live decision snapshots, and
  emergency kill switch closed in code, API key runbook closed in docs, and risk
  profile mismatch closed with a live profile guard. User-data stream is now a
  live gate plus partial implementation: polling is not accepted for live, the
  websocket runner skeleton exists, and live exchange creation stays blocked
  until stream readiness is proven on testnet.
- 2026-05-04 high-return pivot continuation: user reaffirmed the single target
  as `80%+` net annual return with 7x-10x leverage and dynamic risk. Added
  objective chart-pattern features from visual chart research in
  `chart_pattern_features.py`, wired them into `adaptive_decision_report.py`,
  and documented the screenshot-to-feature policy in
  `docs/VISUAL_CHART_PATTERN_RESEARCH_2026_05_04.md`.
- 2026-05-04 social/news context decision: realtime social data must not run
  inside the order loop. Added `social_signal_policy.py` as an async/cacheable
  context scorer. It can produce `observe`, `alert_only`, `paper_long`,
  `paper_short`, or `block`, but `can_open_trade` is always false. Documented
  source access and fail-closed policy in
  `docs/SOCIAL_SIGNAL_POLICY_2026_05_04.md`.
- 2026-05-04 Hurst-MTF Phase A result: implemented additive research-only
  `hurst_gate.py`, `mtf_momentum_signal.py`, `vol_target_sizing.py`, and
  `hurst_mtf_momentum_report.py`. Full strict rerun used fixed 8-perp universe,
  72 candidates, 12 folds, 2400/300 train/test bars, 12-bar purge gap,
  direction-specific 1h trigger volume, severe costs, PBO matrix, concentration,
  tail, and crisis checks. Result is `benchmark_only`: severe total return
  `-95.3959%`, CAGR `-84.6355%`, max DD `98.7345%`, Sortino `-1.5344`,
  2/12 positive folds, DSR proxy `-4.8542`, sample `454` trades. Do not advance
  to Phase B; hand to Claude review if requested.
- 2026-05-05 Hurst-MTF false-negative audit: added
  `hurst_mtf_false_negative_audit.py` and
  `docs/HURST_MTF_FALSE_NEGATIVE_AUDIT_2026_05_05.md`. The external review
  had factual errors: 2024-08-05 crisis alpha was positive, the implied start
  balance was about `5000` not `1000`, and fold 12 was positive despite the
  "folds 6-12 all negative" wording. Artifact recomputation still matched the
  JSON/CSV outputs, baseline compound return was also negative (`-73.7979%`),
  severe compound return remained `-95.3959%`, and status stays
  `benchmark_only`; continue alpha research without promoting Phase B.
- 2026-05-05 Hurst-MTF diagnostics and cooldown V2: added
  `hurst_mtf_trade_diagnostics.py`,
  `docs/HURST_MTF_TRADE_DIAGNOSTICS_2026_05_05.md`,
  `docs/HURST_MTF_COOLDOWN_V2_BRIEF_2026_05_05.md`,
  `docs/HURST_MTF_COOLDOWN_V2_REPORT_2026_05_05.md`, and
  `docs/HURST_MTF_COOLDOWN_V2_DIAGNOSTICS_2026_05_05.md`. Phase A leak:
  hard stops `-27898.1850`, trailing stops `+25565.9561`, losing-exit
  reentries within 24h `-8038.1325`. V2 added `loss_cooldown_bars=6`;
  severe improved to `-70.5401%`, positive folds `4/12`, sample `381`, but
  status remains `benchmark_only` with failed CAGR/PBO/folds/DSR/Sortino/tail/
  crisis gates. Baseline V2 was `+20.5578%` while severe was `-70.5401%`, so
  next brief is `docs/HURST_MTF_COST_ROBUST_V3_BRIEF_2026_05_05.md`: keep
  cooldown and test cost-cushion/turnover reduction. No paper/live promotion.
- 2026-05-05 Hurst-MTF cost-robust V3 result: added explicit V3 candidate grid
  to `hurst_mtf_momentum_report.py` (`--cost-robust-v3`, cost floor
  multipliers `2/3/4`, signal strength mins `0.45/0.55/0.65`) and full strict
  rerun with `648` candidates, `loss_cooldown_bars=6`, fixed 8-perp universe,
  12 folds. Result stayed `benchmark_only`: severe total return `-45.0242%`,
  CAGR `-30.5146%`, max DD `86.2011%`, positive folds `5/12`, PBO `0.3333`,
  DSR proxy `-2.9569`, Sortino `-0.0050`, sample `246`, crisis `2024-08-05`
  positive (`8511.3580`) but `2025-10-10` negative (`-104.1218`). Diagnostic:
  baseline compound `+26.9181%`, severe `-45.0242%`, hard stops `-17641.6079`,
  trailing stops `+22887.4962`, selected next candidate
  `LEAVE_HURST_MTF_FAMILY`. Do not add more Hurst-MTF filters; switch to a
  different alpha family unless a future independent candidate passes strict
  gates. No paper/live promotion.
- 2026-05-05 HTF support/resistance reversion result: added research-only
  `htf_reversion_signal.py`, `htf_reversion_report.py`, tests, and
  `docs/HTF_REVERSION_BRIEF_2026_05_05.md`. Full strict rerun used fixed
  8-perp universe, 324 candidates, 12 folds, 4h support/resistance levels,
  RSI exhaustion, low-ADX range filter, optional volume exhaustion, severe
  cost stress, PBO matrix, concentration, tail, and crisis checks. Result is
  `benchmark_only`: severe total return `-2.0765%`, CAGR `-1.2687%`, max DD
  `11.4489%`, positive folds `5/12`, PBO `0.3333`, DSR proxy `-2.9421`,
  Sortino `-0.0265`, sample `31` trades, no crisis-day trades. The family did
  not blow up, but it is too sparse and too weak for the `80%+` target. No
  paper/live promotion.
- 2026-05-05 Volatility Breakout V1 and regime diagnostic: added research-only
  `volatility_breakout_signal.py`, `volatility_breakout_report.py`,
  `volatility_breakout_regime_diagnostics.py`, tests, and docs. Full strict
  V1 rerun used fixed 8-perp universe, 216 candidates, 1h entries, BTC
  market-leader gate, 4h trend/ADX alignment, 12 folds, severe cost stress,
  and produced `benchmark_only`: severe total return `-73.2745%`, CAGR
  `-55.1919%`, max DD `75.2624%`, positive folds `1/12`, PBO `0.3333`, DSR
  proxy `-8.9916`, Sortino `-1.2828`, sample `296`. Diagnostic checked BTC
  vol/trend/ADX/squeeze/funding by fold. Claude's suggested folds `2,5,10,12`
  do not match the current artifact; current baseline-positive folds are
  `6,7,8,11,12`, severe-positive only `6`. This supports an adaptive
  timeframe/regime-gate hypothesis, but not a paper/live rule yet. Next valid
  experiment is a V2 regime-permission overlay, not arbitrary timeframe
  switching.

## Runtime / Worktree Notes

- A paper runner was restarted after the active DOGE/LINK/TRX symbol change.
  Last verified after the candle-structure report on 2026-05-04 with PID `9400`,
  heartbeat `ok` (`50.55` minutes old at check time), equity `917.811576`,
  wallet `918.776704`, open positions `1`, recent closed trades `2`, testnet
  `true`, live trading approval `false`, and `alert_count=0`. This can go
  stale; verify `paper_heartbeat.json` before relying on it.
- A 2h scaled shadow paper runner was started with:
  `python paper_runner.py --loop --interval-minutes 60 --tag shadow_2h --timeframe 2h --scale-lookbacks`.
  Last verified after the candle-structure report on 2026-05-04 with PID `17316`,
  heartbeat `ok` (`50.56` minutes old at check time), equity `1008.757387`,
  wallet `1008.757387`, open positions `0`, recent closed trades `1`,
  warnings none. It writes isolated files such as
  `paper_shadow_2h_state.json` and can be checked with
  `python paper_report.py --tag shadow_2h`.
- `python paper_decision_report.py --json` compares daily/weekly decision
  windows for default and `shadow_2h`. Last observed daily state on 2026-05-04:
  default 4h had `72` decision rows, `1` paper open, `1` orderbook skip, and no
  closed trades; `shadow_2h` had `72` decision rows, one closed trade, and total
  PnL `8.757387`.
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
   action counts, skips, flow freshness, risk multipliers, open positions,
   trade summaries, and runtime warnings. Use `python paper_decision_report.py`
   for 4h vs 2h daily/weekly comparison.
3. Restart paper/testnet runners only after checking `ops_status.py --json`;
   already-running Python processes may still use the old imported config.
4. Testnet-prove `user_stream_runner.py` before considering any
   `USER_DATA_STREAM_READY=True` change.
5. If continuing the strategy pivot, move beyond simple Binance spot/perp carry:
   research funding prediction, cross-exchange basis/funding, or a stat-arb
   overlay before writing any spot/perp executor.
6. Tune `protections.py` and `exit_ladder.py` parameters only in backtest-only
   mode; current parameters reduce CAGR.
7. Add a real executor-backed paper implementation only after a net-positive
   side-by-side report.
8. Only after net-positive evidence and real fill review, consider live-trading
   gates.

## Do Not Do Without Explicit Approval

- Do not enable live trading.
- Do not disable `TESTNET`.
- Do not enable passive add-ons in live/paper flow without validation.
- Do not change the main signal to grid/DCA/martingale.
- Do not cap upside profits with fixed total-profit limits.
- Do not revert unrelated user or generated changes.
