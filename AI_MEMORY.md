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
  `python -m unittest discover -s tests -v` -> `18` tests OK.
- Portfolio candidate sweep:
  `python portfolio_candidate_sweep.py --years 3 --min-size 3 --max-size 3 --top 30`
  ranked `DOGE/USDT,LINK/USDT,TRX/USDT` first with `264` trades, `83.33%`
  win rate, `11271.76` final equity, `124.21%` CAGR, `5.05%` peak DD, and
  `10.1688` profit factor. Current `SOL/USDT,ETH/USDT,BNB/USDT` ranked `303`
  with `79.54%` CAGR and `7.67%` peak DD. All top 30 rows included `TRX/USDT`,
  so this is a strong research lead but needs out-of-sample validation before
  any config change.

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
  add-on toggles.
- `strategy.py`: main signal and exit logic. Avoid changing this unless the user
  explicitly approves a strategy change and validation is rerun.
- `risk.py`: market, calendar, pattern, flow, and volume-profile risk
  multipliers.
- `execution_guard.py`: wick/spike, hard-stop, mark-price stop, and orderbook
  guard logic.
- `order_manager.py`: live/testnet order placement, one-way mode check, hard
  stop placement, reduce-only close.
- `paper_runner.py`: no-order paper telemetry runner.
- `portfolio_backtest.py`: current primary statistical backtest.
- `portfolio_walk_forward.py`: portfolio walk-forward validation.
- `portfolio_monte_carlo.py`: trade-return Monte Carlo validation.
- `flow_data.py`: Binance public futures flow data with TTL/freshness handling.
- `protections.py`: passive mature-bot protections.
- `exit_ladder.py`: passive partial-TP/breakeven helper.
- `pair_universe.py`: passive dynamic pairlist scoring.
- `twap_execution.py`: passive TWAP slice planner.
- `trade_executor.py`: passive lifecycle contract for future execution refactor.
- `ops_status.py`: local paper/testnet status report.
- `mature_bot_compare.py`: side-by-side add-on validation.
- `portfolio_candidate_sweep.py`: searches better symbol combinations without
  changing the strategy.
- `bias_audit.py`: lookahead/recursive indicator stability audit.
- `docs/MATURE_BOT_ADDONS.md`: activation rules for new add-ons.
- `docs/PORTFOLIO_CANDIDATE_SWEEP.md`: usage and latest smoke result for
  symbol portfolio search.

## Runtime / Worktree Notes

- A paper runner was last observed healthy with PID `11284`, status `ok`,
  equity `1000`, wallet `1000`, open positions `0`, testnet `true`, and
  live trading approval `false`. It started before the active symbol change, so
  restart it before expecting DOGE/LINK/TRX paper decisions. This can go stale;
  verify `paper_heartbeat.json` before relying on it.
- Runtime paper files are ignored by git.
- `walk_forward_results.csv` is a known pre-existing dirty file. Do not stage,
  revert, or rewrite it unless the user specifically asks.
- Large CSV files should not be read wholesale. Use `head`, `tail`,
  `Select-Object -First`, or script summaries.

## Safe Next Steps

1. Run `python portfolio_backtest.py` and unit tests after any active config
   change.
2. Restart paper/testnet runners only after checking `ops_status.py --json`;
   already-running Python processes may still use the old imported config.
3. Tune `protections.py` and `exit_ladder.py` parameters only in backtest-only
   mode; current parameters reduce CAGR.
4. Add a real executor-backed paper implementation only after a net-positive
   side-by-side report.
5. Only after net-positive evidence and real fill review, consider live-trading
   gates.

## Do Not Do Without Explicit Approval

- Do not enable live trading.
- Do not disable `TESTNET`.
- Do not enable passive add-ons in live/paper flow without validation.
- Do not change the main signal to grid/DCA/martingale.
- Do not cap upside profits with fixed total-profit limits.
- Do not revert unrelated user or generated changes.
