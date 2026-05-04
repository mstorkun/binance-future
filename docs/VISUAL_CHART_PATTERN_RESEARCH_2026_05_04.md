# Visual Chart Pattern Research - 2026-05-04

Status: research-only. Internet chart screenshots are not used as trade
signals. They are converted into testable OHLCV features and must pass
walk-forward validation after costs.

## Decision

The bot should not read random screenshot predictions and trade from them.
That is mostly cherry-picked, sometimes repainted, and usually missing cost,
fill, and invalidation context.

Useful part: many visual ideas can be made objective:

- range breakout with close confirmation
- failed wick breakout / fakeout
- breakout retest of prior resistance/support
- resistance and support touch counts
- compression before expansion
- ascending, descending, and symmetric triangle approximations
- flag-style compression after impulse
- measured-move percent from range height

Added `chart_pattern_features.py` for that objective version. It uses closed
candles only, shifts prior ranges before breakout checks, and has no image or
future-bar dependency.

## Bot Use

`adaptive_decision_report.py` now adds chart-pattern features on the base
timeframe and on context frames. The model can learn whether these features add
value instead of hard-coding "triangle means buy" rules.

The right policy is:

1. Treat chart posts and screenshots as hypothesis generators.
2. Translate them into deterministic features.
3. Backtest with fees, slippage, funding, and walk-forward folds.
4. Use them only if they improve expectancy or drawdown out of sample.

## No-Trade Cases

- screenshot has no timestamp, symbol, timeframe, or invalidation level
- prediction depends on future/redrawn trendlines
- target is shown without stop/liquidation distance
- same chart repeats across social channels with copy-paste language
- price already moved hard before the bot sees the post

## Sources

- Binance USD-M kline data: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Kline-Candlestick-Data
- Binance Academy chart patterns: https://academy.binance.com/en/articles/a-beginners-guide-to-classical-chart-patterns
- CME technical analysis overview: https://www.cmegroup.com/education/courses/technical-analysis.html
- Lo, Mamaysky, and Wang chart-pattern research: https://www.nber.org/papers/w7613
- Bulkowski pattern reference: https://thepatternsite.com/
- TradingView repainting discussion: https://www.tradingview.com/pine-script-docs/concepts/repainting/
- CoinMarketCap false breakout explainer: https://coinmarketcap.com/academy/glossary/false-breakout
