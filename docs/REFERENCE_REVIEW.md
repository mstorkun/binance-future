# Reference Review And Stability Plan

Date: 2026-05-01

Purpose: define which external references are worth using while the 4h paper
runner and 2h scaled shadow runner continue. This document does not change the
active strategy. It maps reliable references to concrete gaps in this repo.

## Current Bot Context

- Active mode: paper/testnet research only.
- Active portfolio: `DOGE/USDT`, `LINK/USDT`, `TRX/USDT`.
- Active default timeframe: `4h`.
- Shadow comparison: `2h` with scaled lookbacks.
- Live trading remains blocked by `config.TESTNET = True` and
  `config.LIVE_TRADING_APPROVED = False`.
- Main rule while paper tests run: do not tune the strategy from partial paper
  results. Use this time to harden measurement, execution safety, and recovery.

## Reference Sources To Use

### 1. Binance Official Futures Docs

Use Binance docs as the source of truth for exchange behavior, not examples from
random GitHub bots.

References:

- Exchange filters and symbol rules:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information
- User data order stream:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Event-Order-Update
- Position information:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Position-Information-V3
- Position mode:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Change-Position-Mode
- Leverage:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Change-Initial-Leverage
- ADL quantile:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Position-ADL-Quantile-Estimation

What this should improve in our bot:

- Enforce `PRICE_FILTER`, `LOT_SIZE`, `MARKET_LOT_SIZE`, `MIN_NOTIONAL`, and
  `PERCENT_PRICE` from `exchangeInfo` before placing any order.
- Stop using precision shortcuts as trading rules. Binance explicitly separates
  precision fields from `tickSize` and `stepSize`.
- Track every `ORDER_TRADE_UPDATE`, especially `PARTIALLY_FILLED`, `FILLED`,
  `CANCELED`, `EXPIRED`, reduce-only flag, average price, realized PnL,
  commission, and position side.
- Reconcile REST position snapshots with user data stream updates. Binance says
  position info should be used with the user data stream for timeliness and
  accuracy.
- Confirm one-way mode before trading because our strategy expects
  `positionSide = BOTH`, not hedge-mode long/short buckets.
- Store leverage confirmation per symbol after setting leverage.
- Add an ADL warning field to ops status before live approval.

Repo gap mapping:

- `order_manager.py`: verify symbol filters at startup and before order submit.
- `order_manager.py`: persist order lifecycle events, not just final intent.
- `bot.py`: fail closed if position mode cannot be confirmed.
- `ops_status.py`: include ADL, leverage, position mode, and stale stream state.
- `testnet_fill_probe.py`: compare expected quantity/price with actual fill,
  commission, and realized slippage.

### 2. Freqtrade

Use Freqtrade as a validation-process reference, not as a strategy source.

References:

- Lookahead analysis:
  https://www.freqtrade.io/en/stable/lookahead-analysis/
- Backtesting:
  https://www.freqtrade.io/en/stable/backtesting/
- Strategy callbacks and risk controls:
  https://www.freqtrade.io/en/stable/strategy-callbacks/

What this should improve in our bot:

- Keep `bias_audit.py` as a mandatory gate after indicator or data changes.
- Add a recursive-analysis style check for indicator stability across different
  startup candle counts.
- Export backtest trades in a format that is easy to compare by symbol,
  timeframe, side, signal reason, exit reason, fee, slippage, funding, and
  drawdown at entry.
- Treat every very high backtest as suspicious until it survives walk-forward,
  Monte Carlo, and paper/live parity checks.

Repo gap mapping:

- `bias_audit.py`: add startup-candle sensitivity checks.
- `portfolio_backtest.py`: add richer export columns for entry context.
- `docs/`: add a standard validation report template before any strategy switch.

### 3. NautilusTrader

Use NautilusTrader as an architecture reference for paper/live parity and event
ordering.

References:

- Overview:
  https://nautilustrader.io/docs/latest/concepts/overview/
- Backtesting:
  https://nautilustrader.io/docs/latest/concepts/backtesting/
- Live trading:
  https://nautilustrader.io/docs/latest/concepts/live/

What this should improve in our bot:

- Move toward one lifecycle model for backtest, paper, testnet, and live:
  market data event -> signal -> risk decision -> order intent -> order event ->
  position state -> telemetry.
- Make paper mode consume the same signal/risk/position accounting path as
  testnet as much as possible.
- Make restarts deterministic: on startup, reconcile open orders, open
  positions, local state, and last strategy decision before doing anything new.

Repo gap mapping:

- `trade_executor.py`: promote the passive contract into the future shared
  lifecycle boundary.
- `paper_runner.py`: reduce divergence from the future executor contract.
- `paper_runtime.py`: keep tagged state isolation, but standardize event schema.
- `order_manager.py`: persist idempotency keys and exchange order ids.

### 4. VectorBT And Backtrader

Use these as independent cross-check tools, not as replacements for the current
repo.

References:

- VectorBT docs: https://vectorbt.dev/
- Backtrader docs: https://www.backtrader.com/docu/

What this should improve in our bot:

- Rebuild a simplified version of the current Donchian/ADX/volume/RSI/1D trend
  logic in one independent framework.
- Compare trade count, entry timestamps, exit timestamps, fee assumptions, and
  drawdown shape against `portfolio_backtest.py`.
- If the independent result differs materially, inspect assumptions before
  trusting either result.

Repo gap mapping:

- Add an offline `docs/CROSS_BACKTEST_CHECK.md` after the first independent
  comparison.
- Do not wire VectorBT/Backtrader into the live bot.

### 5. TradingView

Use TradingView as visual audit only. Do not copy public scripts into the bot
without independent testing.

Existing local reference:

- `docs/TRADINGVIEW_INDICATOR_RESEARCH.md`

What this should improve in our bot:

- Manually inspect DOGE/LINK/TRX on 4h and 2h for Donchian breakouts, ADX
  regime, RSI extremes, 1D trend alignment, and major false-breakout zones.
- Compare bot decision timestamps against chart candles.
- Use this to catch obvious data alignment or candle-close mistakes, not to
  overrule the tested strategy.

Repo gap mapping:

- `paper_decisions.csv` and `paper_shadow_2h_decisions.csv`: include enough
  signal context to audit a decision visually without rerunning code.
- `paper_report.py`: add latest candle close, Donchian level, ADX, RSI, volume
  ratio, and 1D trend fields if not already exposed.

### 6. GitHub Repos

Use GitHub repos for operational patterns only. Most public trading bots have
weak risk controls, optimistic backtests, or exchange assumptions that do not
match this project.

Existing local reference:

- `docs/GITHUB_REPO_RESEARCH.md`

Useful patterns to borrow:

- WebSocket reconnect with exponential backoff.
- User data stream keepalive and stale-stream detection.
- Order idempotency and client order id design.
- Partial-fill handling.
- State reconciliation after restart.
- Alerting when telemetry is stale.

Patterns to avoid:

- Martingale, grid averaging, or DCA recovery.
- Fixed total profit caps that cut strong trends.
- Strategies that only work in a narrow hand-picked date range.
- Bots that cancel all orders before confirming current position and reduce-only
  state.

## Prioritized Work While Tests Run

### P0 - Do Before Any Live Consideration

1. Add exchange-filter validation cache from `exchangeInfo`.
2. Add fail-closed position mode check.
3. Add user data stream order-event persistence for testnet/live.
4. Add startup reconciliation: exchange position, open orders, local state,
   last decision, and hard-stop order.
5. Add telemetry alerts for stale heartbeat, stale user stream, missing hard
   stop, wrong position mode, and live approval mismatch.

### P1 - Do Before Increasing Capital

1. Add startup-candle sensitivity to `bias_audit.py`.
2. Add richer paper decision fields for visual TradingView audits.
3. Add independent cross-backtest comparison for the active portfolio.
4. Add ADL and liquidation-distance reporting to `ops_status.py`.
5. Add testnet fill report that records actual average fill price, commission,
   slippage, and reduce-only close behavior.

### P2 - Research Only

1. Compare 4h versus 2h scaled only after at least 24h paper telemetry and then
   longer paper forward testing.
2. Tune mature-bot add-ons only in side-by-side backtest mode.
3. Expand pair universe only after out-of-sample validation.

## Acceptance Gates

The bot should not move from paper/testnet research toward live until all of
these are true:

- `python -m pytest tests/test_safety.py -q` passes.
- `python bias_audit.py` passes for every active symbol.
- Portfolio backtest, walk-forward, and Monte Carlo are still positive after
  any change.
- Paper runner and shadow runner have clean heartbeat and no unexpected errors.
- Testnet fill probe confirms actual fills, commissions, slippage, and
  reduce-only close behavior.
- Startup reconciliation has been tested after intentionally stopping and
  restarting the bot.
- Live approval remains an explicit manual gate, never a default config change.

## Immediate Recommendation

While the current 24h paper test runs, the best next implementation is not a new
indicator. The highest-value stability work is:

1. `exchangeInfo` filter validation.
2. fail-closed position mode and leverage confirmation.
3. persistent order-event tracking from user data stream.
4. richer paper decision telemetry for TradingView visual audit.

These changes make the bot safer without changing the strategy under test.
