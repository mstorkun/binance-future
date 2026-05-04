# Candle, Order-Flow, and Liquidation Research Plan - 2026-05-04

## Objective

The strategy lab objective is unchanged: find a Binance Futures strategy family
that can clear at least `80%` net annualized return after fees, slippage,
funding, and drawdown controls. Capital amount is not the pass metric.
`1000`, `3000`, `5000`, or `7000` USDT are sizing scenarios only; the gate is
percentage performance after costs.

This document is research-only. It does not enable live trading.

The bot should be selective. It does not need to enter quickly just because a
candle closes. If market state, indicators, candle structure, correlation, and
multi-timeframe context do not agree, it waits. Holding/waiting windows are
parameters, not constants; the first proxy screen includes longer horizons such
as `24` and `36` bars in addition to shorter exits.

## 10-Agent Research Summary

1. Classic named candlestick patterns are weak standalone signals. The best
   candidates are selective hourly bearish reversals, 15-minute candle-boundary
   timing effects, and 1-minute consecutive-candle futures patterns.
2. ML research points away from raw pattern names and toward numeric candle
   anatomy: body percent, wick ratios, close location, range/ATR, volume z-score,
   and multi-timeframe context.
3. Liquidation hunting needs real liquidation/OI/funding/orderbook context.
   Binance liquidation streams are incomplete because they publish only the
   largest liquidation snapshot per symbol per 1000 ms.
4. Volume and volatility breakouts are more plausible as continuation signals
   when taker flow and OI agree. Wick rejection and failed breakouts are more
   plausible reversal candidates.
5. Order-flow features are the strongest short-horizon research direction:
   taker imbalance, CVD, trade intensity, depth imbalance, OI change, funding,
   and long/short ratios.
6. BTC-ETH stat-arb is possible but not automatically safe at high leverage.
   Cointegration can break, funding matters, and hedge trades can liquidate
   before convergence.
7. `5%` to `10%` risk per trade is a stress scenario, not a live default. It
   should be tested only with hard drawdown, daily stop, cooldown, and kill
   switch rules.
8. Binance Futures fees are charged on notional, not margin. At 7x-10x leverage,
   frequent taker trades can consume a large share of margin through commission
   alone.
9. Backtests must be treated as falsification tests: walk-forward, final OOS,
   PBO/DSR, Monte Carlo, and 2x-3x slippage sensitivity are required before any
   promotion.
10. Recommended data stack: Binance official API plus local recorder first,
    then Coinalyze/CoinGlass for derivatives context, and only later Velo/Tardis
    if the edge needs deeper 1m/tick/orderbook history.

## Research Families To Test

### A. Candle Anatomy + Cost-Aware No-Trade Model

Use numeric candle features rather than pattern names:

- `body_pct`
- `upper_wick_pct`, `lower_wick_pct`
- `close_location`
- `range_pct`, `range_pct / ATR`
- `volume_z`
- 5m/15m/1h trend and volatility regime

Target: next 3-5 bars. The model must include a `no_trade` zone, so it waits
unless expected move clears fee, spread, slippage, and funding risk.

Decision inputs:

- long/short side is chosen by expected net move, not by candle name
- market regime: trend, range, high-volatility, low-volatility
- correlation state: single-symbol signal or market-wide correlated move
- timeframe agreement: 5m execution, 15m/1h context, 4h/daily risk regime
- no-trade state when signals disagree

### B. Volume Breakout Continuation

Test 15m/1h BTC, ETH, DOGE, LINK, TRX and other liquid USDT perps:

- close beyond prior 20-bar high/low
- volume z-score above threshold
- taker buy/sell imbalance aligned with breakout
- OI rising with price move
- no large opposing wick rejection

Pass condition: net OOS expectancy and CAGR stay positive after taker-cost and
2x slippage stress.

### C. Failed Breakout / Wick Reversal

Test 5m/15m liquid alts:

- price breaks a recent high/low
- candle closes back inside the range
- wick/range ratio is high
- liquidation or volume spike confirms forced flow
- entry waits for next-bar confirmation, not the same candle

This is the closest direct continuation of "mum şekli" research, but the signal
must be filtered by volume/OI/order-flow.

### D. Liquidation Cascade Reversal / Continuation

Current implementation starts with an OHLCV proxy only:

- large directional candle
- abnormal volume
- expanded range
- next-bar entry
- conservative stop-first intrabar assumption
- cooldown and max-trades-per-day to avoid churn
- configurable horizon grid so the bot can wait longer when the setup needs it

Second pass must add real liquidation/OI data through Binance live recording,
Coinalyze, or CoinGlass before any paper promotion.

### E. Order-Flow Microstructure

Use Binance `aggTrade`, depth, OI, taker buy/sell, funding, and long/short data:

- 30s-5m taker imbalance
- CVD burst
- orderbook depth imbalance
- OI change
- funding crowding
- top-trader vs global long/short divergence

This is the best candidate for short, selective futures trades, but it needs a
local data recorder because Binance historical derivatives stats are shallow.

## Hard Gates

A candidate can only move from research to paper if it clears all base gates:

- Net CAGR at least `80%`
- Profit factor at least `1.2`
- Enough trades across multiple OOS windows
- Max drawdown within configured mandate
- Positive after fees, spread, slippage, and funding assumptions
- Positive under 2x slippage stress
- No dependency on one single lucky OOS window
- Cooldown and per-day trade cap enabled
- No live trading while audit P0 blockers remain open

## Current Next Step

Run the liquidation proxy as a fast first-pass screen with `3%`, `5%`, and
`10%` risk-per-trade scenarios. Risk changes are diagnostic only; the pass/fail
gate remains net `80%+` annualized return after costs.

If the proxy produces zero passing rows, do not stop the high-return objective.
Move to data collection and order-flow/OI/liquidation features, because the
agent research says raw candle shape alone is not enough.

## Source Pointers

- Binance liquidation stream:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Liquidation-Order-Streams
- Binance order book:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Order-Book
- Binance commission rate:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/User-Commission-Rate
- Binance open interest:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest
- Binance taker buy/sell volume:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Taker-BuySell-Volume
- Binance public data:
  https://github.com/binance/binance-public-data
- Coinalyze API:
  https://api.coinalyze.net/v1/doc/
- CoinGlass API:
  https://docs.coinglass.com/v3.0/reference/getting-started-with-your-api
- Probability of Backtest Overfitting:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
- Deflated Sharpe Ratio:
  https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2460551_code87814.pdf?abstractid=2460551&mirid=1
