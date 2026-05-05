# Volatility Breakout V1 Brief - 2026-05-05

Status: research-only candidate. This does not enable paper, testnet, or live execution.

## Why This Candidate Exists

The last two families gave clear information:

- Hurst-MTF trend following created too much adverse cost and drawdown.
- HTF support/resistance reversion kept drawdown modest but produced only
  `31` severe trades and did not approach the `80%+` target.

Volatility Breakout V1 tests the middle ground:

- wait through low-volatility compression,
- require a real volume-confirmed breakout,
- require 4h trend and BTC market-leader context to agree,
- use trailing exits instead of fixed small take-profit exits.

## Rule Family

Fixed universe:

- `BTC/USDT:USDT`
- `ETH/USDT:USDT`
- `SOL/USDT:USDT`
- `BNB/USDT:USDT`
- `XRP/USDT:USDT`
- `AVAX/USDT:USDT`
- `LINK/USDT:USDT`
- `DOGE/USDT:USDT`

Inputs:

- 1h Binance Futures OHLCV.
- 4h EMA21/55 side and ADX.
- 1d EMA200 side.
- BTC 1h EMA50/200 side, 4h return, and shock z-score.
- 1h Bollinger bandwidth percentile as the squeeze detector.
- 1h prior range breakout over 24, 48, or 72 bars.
- 1h volume z-score.

Entry logic:

- Long: recent squeeze, current closed 1h candle broke prior range high with
  volume, 4h side is long, 1d side is not bearish, and BTC side is not bearish.
- Short: recent squeeze, current closed 1h candle broke prior range low with
  volume, 4h side is short, 1d side is not bullish, and BTC side is not bullish.
- Entry happens on the next 1h open, so signals use closed data only.

Risk/exit logic:

- Vol-targeted sizing with 10x leverage cap.
- Max 20% equity margin per position.
- Max 4 concurrent positions.
- ATR hard stop.
- Trailing stop after the trade reaches 1R.
- Time stop after 36 hours if it never reaches 1R.

## Strict Gate

Same strict gate as the previous candidates:

- Net CAGR after severe cost stress `>=80%`.
- PBO `<0.3`.
- Walk-forward positive folds `>=7/12`.
- DSR proxy `>=0`.
- Sortino `>=2.0`.
- No symbol over `40%` of positive PnL.
- No month over `25%` of positive PnL.
- Tail capture `50-80%`.
- Crisis alpha positive on `2024-08-05` and `2025-10-10`.
- Sample `>=200` trades.

## Decision Rule

If V1 fails, it stays `benchmark_only`. Do not connect it to paper/live
behavior unless every strict gate passes first.

