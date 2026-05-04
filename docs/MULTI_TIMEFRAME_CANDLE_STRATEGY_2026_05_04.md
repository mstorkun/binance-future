# Multi-Timeframe Candle Strategy - 2026-05-04

Status: research-only. This does not approve paper/testnet/live execution.

User target: Binance Futures bot with 7x-10x leverage and at least 80% net
annual return after costs. The candle layer is designed to reduce bad trades
and fee churn; it is not treated as proof of alpha.

## Research Decision

Weekly, daily, hourly, and minute candles can give the bot a usable opinion,
but only as a top-down permission system:

1. Weekly/daily decide the main trade permission: long-only, short-only,
   reduced-size both, or no-trade.
2. 4h/1h decide whether the current intraday structure agrees with that regime.
3. 15m/5m/1m decide only the trigger quality and entry timing.
4. A naked 1m or 5m candle signal is blocked when higher-timeframe context is
   missing or conflicting.

The practical aim is not "predict every next candle." The edge, if it exists,
should show up as fewer weak trades, fewer late chases, lower drawdown, and a
better fee-adjusted R distribution.

## Strategy Preset

Strategy name: `HTF Context Futures Bot`.

Initial markets: BTCUSDT and ETHUSDT first, then only the highest-liquidity
alts after symbol-level validation.

Timeframes:

| Layer | Timeframes | Job |
|---|---|---|
| Regime | 1w, 1d | Decide long/short/no-trade permission |
| Structure | 4h, 1h | Confirm trend, range, breakout, pullback, rejection |
| Setup | 15m, 5m | Sweep, failed breakout, impulse, retest quality |
| Execution | 1m | Fine entry only after parent setup exists |

## Bot Rules

Longs are preferred only when weekly/daily are bullish or at least not
conflicting, 4h/1h do not oppose the trade, and the trigger candle confirms
acceptance/reclaim. Shorts are symmetric.

Hard no-trade cases:

- Weekly and daily candle bias conflict.
- Weekly and daily are both inside-bar compression.
- Weekly/daily outside bar closes in the middle of its range.
- Daily candle is already in extreme same-direction expansion.
- 4h and 1h are both strongly against the proposed side.
- Only minute/trigger candle is bullish/bearish but higher context is missing.

Risk reduction cases:

- Weekly or daily inside bar without confirmed breakout.
- One of 4h/1h conflicts with the side.
- Trigger candle is against the side.
- Higher timeframe is neutral and the setup is only low-timeframe.

Small research-only risk increase is allowed only when weekly, daily, 4h, 1h,
and trigger context are aligned. The current cap in code is `1.30x` of the
adaptive model's risk fraction, still bounded by the configured max risk.

## Implemented

Added `multi_timeframe_candle.py`.

It creates closed-candle features:

- body percent and body ATR
- upper/lower wick percent
- close location
- inside/outside bars
- bullish/bearish engulfing
- breakout up/down against recent structure
- EMA stack and slope
- ATR/range/volume ratios
- candle bias, confidence, and reasons

It also exposes `multi_timeframe_candle_decision(row, side=...)`, returning:

- `permission`: `long_only`, `short_only`, `both_allowed`, or `no_trade`
- `multiplier`: dynamic risk multiplier
- `block_new_entries`: hard block flag
- `bias`, `confidence`, and reason codes

`adaptive_decision_report.py` now adds these features for base candles and
context frames. Default context frames are now `1h`, `4h`, `1d`, and `1w`.
The adaptive model can be run with `--disable-mtf-gate` for ablation.

## Validation Plan

Minimum comparison set:

1. Adaptive model without MTF candle gate.
2. Adaptive model with 4h/1h only.
3. Adaptive model with 1w/1d/4h/1h.
4. Same model delayed by one base candle.
5. Same model with 1.5x and 2x modeled fees/slippage.

Pass criteria before even paper promotion:

- Net CAGR candidate remains above the 80% target after costs.
- Profit factor stays above 1.2 out of sample.
- Max drawdown stays inside the configured limit.
- No single symbol/month explains most profit.
- MTF gate improves drawdown or expectancy versus trigger-only baseline.
- Results survive walk-forward and parameter perturbation.

## Sources

- Binance USD-M kline REST data: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Kline-Candlestick-Data
- Binance USD-M kline stream close-state field: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Kline-Candlestick-Streams
- Freqtrade lookahead-bias analysis: https://www.freqtrade.io/en/stable/lookahead-analysis/
- scikit-learn `TimeSeriesSplit`: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- Fidelity ATR guide: https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr
