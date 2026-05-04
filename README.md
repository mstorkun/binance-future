# Binance Futures Trading Bot

A 4-hour Donchian breakout trend-following bot for Binance Futures.

> **Status:** Research and testing phase. The backtest infrastructure has matured, but the bot is **not** ready for live trading. Start with [docs/MULTI_SYMBOL.md](docs/MULTI_SYMBOL.md) and [docs/WALK_FORWARD.md](docs/WALK_FORWARD.md) for the latest decision context.

## Quick Overview

| Item | Value |
|---|---|
| Target capital | 1,000 USDT |
| Primary timeframe | 4 hours |
| Higher timeframe filter | 1D EMA50; weekly trend context calculated but not enforced |
| Leverage | 10x testnet candidate |
| Risk per trade | 4% base on first open position, correlation-aware after that |
| Primary signal | Donchian breakout |
| Filters | Volume, ADX, RSI, 1D trend, calendar/news risk, volume profile, candlestick context, futures flow context |
| Exits | ATR initial SL, dynamic trailing SL, Donchian exit |
| Mature-bot add-ons | Protection layer, exit ladder, pair universe, TWAP planner, executor contract, bias audit are present but passive by default |

## Strategy

**Entry logic:**

1. The 4H close breaks the prior Donchian channel.
2. The bar volume is above a multiple of the 20-bar moving average.
3. ADX is above the trend-strength threshold.
4. RSI is not in extreme overbought/oversold territory.
5. The 1D trend filter confirms the same direction.
6. Candlestick/price-action patterns and futures-flow context can adjust risk sizing; they do not create standalone trades.

**Exit logic:**

- Initial stop-loss: ATR-based.
- Trailing stop: locks in a portion of the gains.
- Early exit: a shorter Donchian channel breaks in the opposite direction.

## Current Findings

- The current candidate is the DOGE/LINK/TRX `growth_70_compound` portfolio profile.
- Latest 3-year candidate sweep/backtest: about `+124.21% CAGR` with `5.05%` peak drawdown.
- 2026-05-04 critical audit status: the high CAGR is research/backtest evidence,
  not a live expectation. Bonferroni/deflated-Sharpe and holdout degradation keep
  the Donchian system in benchmark mode while funding-rate carry research starts.
- Candidate portfolio walk-forward: fixed growth profile is positive in `7/7` test periods, with `20.12%` average test return and `5.25%` worst test return.
- Full PBO matrix: [docs/PBO_FULL_RESULT_2026_05_02.md](docs/PBO_FULL_RESULT_2026_05_02.md) tested `216` candidates per fold; PBO is `0.1429`, selected candidates were OOS top-half in `6/7` folds, and selected test folds were positive in `7/7`.
- Candidate Monte Carlo: block bootstrap ending-equity p05 is `6191.14` from `1000` start, ending-equity loss probability is `0%`, and peak-DD p95 is `6.25%`.
- Timeframe research: [docs/TIMEFRAME_SWEEP.md](docs/TIMEFRAME_SWEEP.md) shows 1h is not robust after horizon scaling, while 2h is a stronger but higher-drawdown candidate than the current 4h default.
- Stability references: [docs/REFERENCE_REVIEW.md](docs/REFERENCE_REVIEW.md) maps Binance/Freqtrade/NautilusTrader/TradingView/GitHub references to concrete safety and validation work while paper tests run.
- Critical audit: [docs/CRITICAL_AUDIT_2026_05_01.md](docs/CRITICAL_AUDIT_2026_05_01.md) records the latest no-go review and separates confirmed blockers from claims that still need evidence.
- Audit diff: [docs/AUDIT_DIFF_2026_05_01.md](docs/AUDIT_DIFF_2026_05_01.md) merges Claude/Codex disagreements and newly surfaced P0/P1 blockers.
- API key runbook: [docs/API_KEY_SECURITY_RUNBOOK_2026_05_01.md](docs/API_KEY_SECURITY_RUNBOOK_2026_05_01.md) defines live/testnet key scope, trusted-IP policy, and rotation.
- Risk profile policy: [docs/RISK_PROFILE_POLICY_2026_05_01.md](docs/RISK_PROFILE_POLICY_2026_05_01.md) marks the current 10x/%4 profile as research-only and gates live mode to `balanced_live_v1`.
- User-data stream decision: [docs/USER_DATA_STREAM_DECISION_2026_05_01.md](docs/USER_DATA_STREAM_DECISION_2026_05_01.md) rejects polling-only live operation and keeps live mode blocked until stream readiness is proven.
- User-data stream runner: [docs/USER_STREAM_RUNNER_2026_05_04.md](docs/USER_STREAM_RUNNER_2026_05_04.md) adds a websocket consumer skeleton with duplicate/out-of-order guards, keepalive/reconnect timing, and local `live_state` reconciliation plumbing; it is not testnet-proven yet.
- Post-audit actions: [docs/POST_AUDIT_ACTIONS_2026_05_04.md](docs/POST_AUDIT_ACTIONS_2026_05_04.md) records the safety fixes, live preflight, same-bar guard, and funding-carry research lane added after the 12-agent audit.
- Funding carry research: [docs/CARRY_RESEARCH_2026_05_04.md](docs/CARRY_RESEARCH_2026_05_04.md) scanned liquid spot-backed USDT perpetuals over 180 days; static carry and dynamic entry/exit threshold grids both produced `0` passing candidates, so no carry executor should be built yet.
- Trend quality report: [docs/TREND_QUALITY_REPORT_2026_05_04.md](docs/TREND_QUALITY_REPORT_2026_05_04.md) confirms that long/short capability does not remove the need for strong trend context; `market:trend` trades had higher mean return than the full trade set, so trend-quality changes stay report-only until validated side-by-side.
- Candle structure report: [docs/CANDLE_STRUCTURE_REPORT_2026_05_04.md](docs/CANDLE_STRUCTURE_REPORT_2026_05_04.md) adds a separate candle-density/length/correlation diagnostic; aligned candle-structure bias had higher mean return than the full set, but it remains report-only.
- Candle/correlation reducer: [docs/CANDLE_CORRELATION_OVERLAY_2026_05_04.md](docs/CANDLE_CORRELATION_OVERLAY_2026_05_04.md) tests a train-gated risk reducer that never boosts size and only cuts setup buckets proven bad in train; latest OOS pass learned no bad buckets, so it made no paper/testnet/live change.
- Trend/candle entry walk-forward: [docs/TREND_CANDLE_ENTRY_WALK_FORWARD_2026_05_04.md](docs/TREND_CANDLE_ENTRY_WALK_FORWARD_2026_05_04.md) applies the same train-gated reducer at true entry-time sizing; latest OOS pass again learned `0` bad buckets and reduced `0` trades, so there is still no activation case.
- Paper runtime reporting: [docs/PAPER_RUNTIME_REPORTING_2026_05_04.md](docs/PAPER_RUNTIME_REPORTING_2026_05_04.md) separates paper-state alerts from live-state mismatches and adds open-position, recent-trade, MAE/MFE, and 4h-vs-2h daily/weekly reporting.
- Risk-adjusted metrics: [docs/RISK_ADJUSTED_METRICS_2026_05_01.md](docs/RISK_ADJUSTED_METRICS_2026_05_01.md) adds Sharpe/Sortino/Calmar reporting and Bonferroni visibility for candidate sweeps.
- Correlation stress: [docs/CORRELATION_STRESS_2026_05_01.md](docs/CORRELATION_STRESS_2026_05_01.md) adds report-only pairwise symbol correlation stress before any covariance-aware sizing change.
- Pattern ablation: [docs/PATTERN_ABLATION_2026_05_01.md](docs/PATTERN_ABLATION_2026_05_01.md) adds report-only pattern-risk on/off comparison before any pattern-weight claim.
- Exchange filter cache: [docs/EXCHANGE_FILTER_CACHE_2026_05_01.md](docs/EXCHANGE_FILTER_CACHE_2026_05_01.md) adds TTL refresh for Binance symbol filters.
- Paper telemetry atomicity: [docs/PAPER_TELEMETRY_ATOMICITY_2026_05_01.md](docs/PAPER_TELEMETRY_ATOMICITY_2026_05_01.md) flushes/fsyncs paper CSV appends.
- Stale risk quarantine: [docs/STALE_RISK_CODE_QUARANTINE_2026_05_01.md](docs/STALE_RISK_CODE_QUARANTINE_2026_05_01.md) makes the old `risk_management.py` helper fail loudly.
- Passive execution guardrails: [docs/PASSIVE_EXECUTION_GUARDRAILS_2026_05_01.md](docs/PASSIVE_EXECUTION_GUARDRAILS_2026_05_01.md) marks TWAP/executor helpers as research-only and tests that they are not wired into order flow.
- Dependency pinning: [docs/DEPENDENCY_PINNING_2026_05_01.md](docs/DEPENDENCY_PINNING_2026_05_01.md) pins runtime packages, including `ccxt==4.5.51`.
- Paper lock heartbeat: [docs/PAPER_LOCK_HEARTBEAT_2026_05_01.md](docs/PAPER_LOCK_HEARTBEAT_2026_05_01.md) refreshes the paper runner lock while long loops are alive.
- Overfit controls: [docs/OVERFIT_CONTROLS_2026_05_01.md](docs/OVERFIT_CONTROLS_2026_05_01.md) adds Bonferroni Sharpe haircut and walk-forward degradation proxies.
- Bias audit report: [docs/BIAS_AUDIT_REPORT_2026_05_01.md](docs/BIAS_AUDIT_REPORT_2026_05_01.md) commits reproducible lookahead/recursive drift results for DOGE/LINK/TRX.
- Executor refactor decision: [docs/EXECUTOR_REFACTOR_DECISION_2026_05_01.md](docs/EXECUTOR_REFACTOR_DECISION_2026_05_01.md) keeps passive executor/TWAP helpers quarantined until user-data stream and fill reconciliation exist.
- PBO matrix harness/result: [docs/PBO_MATRIX_HARNESS_2026_05_01.md](docs/PBO_MATRIX_HARNESS_2026_05_01.md) adds the matrix path; [docs/PBO_FULL_RESULT_2026_05_02.md](docs/PBO_FULL_RESULT_2026_05_02.md) records the first full result.
- User-stream parser: [docs/USER_STREAM_EVENT_PARSER_2026_05_01.md](docs/USER_STREAM_EVENT_PARSER_2026_05_01.md) parses Binance `ORDER_TRADE_UPDATE` events into local order-event telemetry.
- User-stream listenKey helpers: [docs/USER_STREAM_LISTEN_KEY_2026_05_01.md](docs/USER_STREAM_LISTEN_KEY_2026_05_01.md) adds start/keepalive URL state helpers without opening a websocket.
- User-stream reconcile: [docs/USER_STREAM_RECONCILE_2026_05_01.md](docs/USER_STREAM_RECONCILE_2026_05_01.md) adds conservative local position reconciliation decisions for parsed stream events.
- User-stream runtime handler: [docs/USER_STREAM_RUNTIME_HANDLER_2026_05_01.md](docs/USER_STREAM_RUNTIME_HANDLER_2026_05_01.md) persists parsed/reconciled order updates into `live_state`.
- Verdict: testnet/paper only. Live trading remains blocked until real fills, order-book guard logs, futures-flow logs, and news-event controls are reviewed.

## Files

```text
config.py                    Parameters
data.py                      Live data and exchange queries
indicators.py                ATR, RSI, ADX, Donchian, daily trend
strategy.py                  Signal and exit rules
risk.py                      Position size and SL/TP calculation
pattern_signals.py           Rule-based candlestick/price-action context
flow_data.py                 Futures flow context for live/testnet risk decisions
candle_structure.py          Closed-candle length/density/correlation features
protections.py               Passive mature-bot protection checks
exit_ladder.py               Passive partial-TP/breakeven plan helper
pair_universe.py             Passive dynamic pairlist/liquidity/volatility scoring
twap_execution.py            Passive TWAP slice planner
trade_executor.py            Passive lifecycle contract for future execution refactor
bias_audit.py                Lookahead/recursive indicator stability audit
bias_audit_report.py         Reproducible multi-symbol bias-audit artifact writer
ops_status.py                Local paper/testnet status report
emergency_kill_switch.py     Dry-run-first emergency cancel/close CLI
runtime_guards.py            Persistent trading-disabled flag helpers
go_live_preflight.py         Fail-closed live readiness preflight report
carry_research.py            Research-only funding-rate carry scanner
trend_quality_report.py      Report-only trade attribution by trend-quality context
candle_structure_report.py   Report-only candle-structure attribution
candle_correlation_overlay.py Backtest-only train-gated candle/correlation risk reducer
trend_candle_entry_walk_forward.py True entry-time trend/candle reducer WF
user_stream_client.py        Binance user-stream listenKey lifecycle helpers
user_stream_events.py        Binance user-stream ORDER_TRADE_UPDATE parser
user_stream_reconcile.py     Conservative user-stream position-state decisions
user_stream_runtime.py       Single-message user-stream live_state handler
user_stream_runner.py        User-data stream websocket consumer skeleton
paper_report.py              Detailed paper decision/equity/error report
paper_decision_report.py     Daily/weekly paper decision comparison report
paper_runtime.py             Tagged paper/shadow runtime isolation helpers
mature_bot_compare.py        Side-by-side add-on validation
portfolio_candidate_sweep.py Search better symbol combinations
timeframe_sweep.py           Compare 1h/2h/4h with raw and scaled indicator horizons
risk_metrics.py              Risk-adjusted metric helpers
risk_adjusted_report.py      JSON report for Sharpe/Sortino and multiple-testing visibility
pbo_report.py                PBO-style report from candidate-by-fold matrix
correlation_stress.py        Report-only pairwise symbol correlation stress
pattern_ablation.py          Report-only pattern-risk on/off ablation
portfolio_param_walk_forward.py Train-only portfolio parameter walk-forward
portfolio_cost_stress.py       Replay selected WF folds under harsher costs
portfolio_holdout.py          Final pre-holdout selection and holdout replay
paper_runner.py              No-order paper telemetry and virtual portfolio runner
testnet_fill_probe.py        Explicitly approved testnet fill/slippage probe
order_manager.py             Order placement, SL update, position close
bot.py                       Multi-symbol portfolio bot loop (testnet/live)
backtest.py                  Single-symbol backtest
optimize.py                  Parameter sweep
walk_forward.py              Single-symbol walk-forward
multi_symbol_backtest.py     Multi-symbol straight backtest
multi_symbol_walk_forward.py Multi-symbol walk-forward
monte_carlo.py               Monte Carlo trade-shuffle
docs/                        Review and result reports
```

## Setup

```bash
pip install -r requirements-dev.txt
cp .env.example .env
python backtest.py
python walk_forward.py
python multi_symbol_backtest.py
python multi_symbol_walk_forward.py
python monte_carlo.py --trades backtest_results.csv
python bias_audit.py --symbol DOGE/USDT --years 1 --sample-step 96
python bias_audit.py --symbol LINK/USDT --years 1 --sample-step 96
python bias_audit.py --symbol TRX/USDT --years 1 --sample-step 96
python mature_bot_compare.py --years 3
python portfolio_candidate_sweep.py --years 3 --min-size 3 --max-size 5 --top 20
python risk_adjusted_report.py
python correlation_stress.py --years 3
python pattern_ablation.py --years 3
python timeframe_sweep.py --years 3 --timeframes 1h 2h 4h --scaled-params
python portfolio_param_walk_forward.py --years 3 --max-param-combos 6
python portfolio_cost_stress.py --wf-results portfolio_param_walk_forward_risk_capped_results.csv --years 3
python portfolio_holdout.py --years 3 --holdout-bars 500 --max-param-combos 6
python ops_status.py --json
python go_live_preflight.py --json
python carry_research.py --auto-universe --days 180 --min-quote-volume-usdt 50000000 --max-symbols 80 --dynamic-enter-grid 0.00005 0.000075 0.0001 0.00015 --dynamic-exit-grid 0 0.00002 0.00005 --out carry_candidates.csv --universe-out carry_universe.csv --json
python trend_quality_report.py --trades portfolio_trades.csv --md-out docs/TREND_QUALITY_REPORT_2026_05_04.md --json-out trend_quality_report.json
python candle_structure_report.py --trades portfolio_trades.csv --years 3 --md-out docs/CANDLE_STRUCTURE_REPORT_2026_05_04.md --json-out candle_structure_report.json
python candle_correlation_overlay.py --trades portfolio_trades.csv --years 3
python trend_candle_entry_walk_forward.py --years 3
python emergency_kill_switch.py --json
python paper_report.py
python paper_decision_report.py
python paper_decision_report.py --json
python paper_runner.py --once --reset
python paper_runner.py --loop --interval-minutes 60 --tag shadow_2h --timeframe 2h --scale-lookbacks --reset
python paper_report.py --tag shadow_2h
python user_stream_runner.py --dry-run
python -m unittest discover -s tests -v
```

For the live/testnet bot, place your API keys in `.env` or environment variables. **Do not switch off `config.TESTNET = True` without going through the gating criteria.**

## Python Version

Python 3.10+ is required (the codebase uses PEP 604 union types such as `pd.DataFrame | None`).

## Safety Notice

This repository is **not** investment advice. Futures trading carries leverage, liquidation, funding, slippage, and API/connectivity risks. Before any live trading, the following stages are mandatory: testnet, paper trading, alarm/monitoring, and a small-capital ramp-up.
