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

- Portfolio candidate: `SOL/USDT`, `ETH/USDT`, `BNB/USDT`.
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

The mature-bot add-ons are intentionally passive. Do not wire them into live or
paper order behavior until a side-by-side backtest/walk-forward/Monte Carlo
report proves they are net-positive.

## Latest Validated Results

Most recent validated portfolio backtest after passive mature-bot add-ons:

- command: `python portfolio_backtest.py`
- trades: `244`
- win rate: `82.0%`
- final equity: `5786.96 USDT`
- total return: `+478.70% / 3 years`
- CAGR: `+79.54%/year`
- peak drawdown: `7.7%`
- commission included: `566.17`
- slippage included: `1061.56`
- funding included: `+33.48`

Other previous validation context:

- Portfolio walk-forward fixed growth profile was positive in `7/7` windows.
- Monte Carlo remained acceptable on the current trade set, but bootstrap/block
  drawdown is still a required live gate.
- Bias audit on SOL 1-year data passed:
  `python bias_audit.py --symbol SOL/USDT --years 1 --sample-step 96`
  returned `OK - no indicator drift detected`.
- Unit tests passed:
  `python -m unittest discover -s tests -v` -> `12` tests OK.

## Recent Commits

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
- `bias_audit.py`: lookahead/recursive indicator stability audit.
- `docs/MATURE_BOT_ADDONS.md`: activation rules for new add-ons.

## Runtime / Worktree Notes

- A paper runner was last observed healthy with PID `11284`, status `ok`,
  equity `1000`, wallet `1000`, open positions `0`. This can go stale; verify
  `paper_heartbeat.json` before relying on it.
- Runtime paper files are ignored by git.
- `walk_forward_results.csv` is a known pre-existing dirty file. Do not stage,
  revert, or rewrite it unless the user specifically asks.
- Large CSV files should not be read wholesale. Use `head`, `tail`,
  `Select-Object -First`, or script summaries.

## Safe Next Steps

1. Build a side-by-side backtest-only comparison for `protections.py`.
2. Separately test `exit_ladder.py` in backtest-only mode.
3. Run portfolio walk-forward for any active change.
4. Run Monte Carlo bootstrap/block for any active change.
5. Only after net-positive evidence, consider paper/testnet wiring.

## Do Not Do Without Explicit Approval

- Do not enable live trading.
- Do not disable `TESTNET`.
- Do not enable passive add-ons in live/paper flow without validation.
- Do not change the main signal to grid/DCA/martingale.
- Do not cap upside profits with fixed total-profit limits.
- Do not revert unrelated user or generated changes.
