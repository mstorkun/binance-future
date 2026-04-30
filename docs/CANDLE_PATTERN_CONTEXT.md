# Candle Pattern Context

`pattern_signals.py` converts common visual candlestick ideas into deterministic
OHLCV rules. It is intentionally a context layer, not a standalone prediction
engine.

## Implemented Patterns

| Pattern | Rule summary | Column |
|---|---|---|
| Liquidity sweep | Price breaks prior rolling high/low, closes back inside, has dominant wick and higher volume | `pattern_liquidity_sweep` |
| Wick rejection | Large upper/lower wick relative to body and candle range | `pattern_wick_rejection` |
| Strong impulse | Large body, ATR-sized range, closes near the candle extreme, volume confirms | `pattern_impulse` |
| Engulfing | Current real body engulfs the previous opposite body | `pattern_engulfing` |
| Inside-bar breakout | Previous candle is inside its parent, current close breaks it with volume | `pattern_inside_breakout` |

## How It Affects The Bot

- Patterns are calculated from closed candles only.
- They produce long/short scores and `pattern_bias`.
- `risk.entry_risk_decision()` uses the bias as a small risk multiplier:
  - aligned pattern: modestly increases risk;
  - opposing pattern: no penalty by default;
  - strong opposing pattern can block entries, but that is disabled by default.
- The module does not force a trade direction and does not override Donchian,
  daily-trend, calendar, volume-profile, slippage, funding, or commission logic.

## Validation Rule

Keep this layer only if the portfolio backtest, walk-forward, and Monte Carlo
results remain acceptable. If CAGR improves but drawdown or Monte Carlo tail
risk worsens materially, use the patterns only as risk reducers or disable
`PATTERN_RISK_ENABLED`.

## Latest Validation

The first penalty-based version reduced CAGR. The current align-only version was
kept because it preserved the drawdown band and slightly improved the corrected
portfolio backtest:

- Growth candidate CAGR: `79.54%`
- Peak drawdown: `7.67%`
- Walk-forward fixed growth periods: `7/7` positive
