# BTC Market Leader Overlay - 2026-05-04

## Objective

BTC is the market locomotive for many crypto futures regimes. The bot should
not blindly copy BTC, but it should know whether an altcoin signal is aligned
with BTC, fighting BTC, or genuinely decoupled.

This layer is research-only. It does not enable live trading.

## Core Design

Use BTC as a market-regime and risk-permission layer:

`BTC regime -> beta-adjusted alt residual -> relative strength -> dynamic risk`

The altcoin still needs its own candle/indicator/order-flow setup. BTC only
changes permission, risk, and feature context.

## Implemented First Pass

`btc_market_leader.py` adds:

- BTC 1/3/12-bar returns
- BTC trend strength and trend slope
- BTC realized volatility
- BTC shock z-score
- rolling alt-BTC correlation
- rolling beta
- beta-adjusted residual return
- alt relative strength versus BTC

It returns a soft decision:

- `multiplier > 1`: BTC supports the requested side
- `0 < multiplier < 1`: BTC is mixed, decoupled, or mildly against
- `block_new_entries=True`: BTC shock is strongly against the alt trade

These features are also joined into `adaptive_decision_report.py`, so the
adaptive model can learn whether BTC context improves long/short/wait decisions.

## Decision Logic

| BTC state | Alt long | Alt short |
|---|---|---|
| BTC bullish, correlated alt | allowed/boosted if alt setup confirms | reduced or blocked |
| BTC bearish, correlated alt | reduced or blocked | allowed/boosted if alt setup confirms |
| BTC shock against trade | no new entry | no new entry |
| BTC shock with trade | reduce chasing risk; require confirmation | reduce chasing risk; require confirmation |
| BTC decoupled | reduce risk unless residual strength is strong | reduce risk unless residual weakness is strong |

## Feature Hypotheses

1. Alt longs perform better when BTC 1h/4h regime is bullish or recovering.
2. Alt shorts perform better when BTC 1h/4h regime is bearish or failed-rally.
3. BTC shock z-score above `2` should stop adding high-beta alt exposure.
4. Beta-adjusted residual return is better than raw alt momentum.
5. High rolling correlation means many alt positions are one hidden BTC trade.
6. Decoupling is tradable only when volume/OI confirms and BTC shock is low.
7. A long in an alt underperforming BTC should be smaller or skipped.
8. A short in an alt outperforming BTC should be smaller or skipped.

## Validation Plan

Compare these variants:

1. baseline alt strategy
2. baseline + BTC trend gate
3. baseline + BTC volatility/shock gate
4. baseline + BTC beta/residual features
5. baseline + BTC gate + macro/news gate
6. adaptive model with BTC features

Pass/fail metrics:

- net CAGR target remains `>=80%` after costs
- max drawdown improves or does not worsen materially
- liquidation/shock-day losses decrease
- no single BTC regime provides most PnL
- OOS folds show improvement, not just one lucky period
- 2x slippage stress remains positive

## Sources

- Binance USD-M klines:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Kline-Candlestick-Data
- Binance kline streams:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Kline-Candlestick-Streams
- Binance mark price/funding:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Mark-Price-Stream
- Binance open interest:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest
- Binance liquidation streams:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Liquidation-Order-Streams
- CoinGecko global market/dominance data:
  https://docs.coingecko.com/docs/market-research
- Engle DCC correlation model:
  https://pages.stern.nyu.edu/~rengle/dccfinal.pdf
- Pairs trading relative value reference:
  https://depot.som.yale.edu/icf/papers/fileuploads/2573/original/08-03.pdf
