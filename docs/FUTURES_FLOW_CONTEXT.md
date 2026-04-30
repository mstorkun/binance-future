# Futures Flow Context

Date: 2026-05-01

`flow_data.py` adds Binance USD-M futures flow context as an optional risk
overlay. It is designed for live/testnet decisions first, because several
public futures-data endpoints expose only a recent window.

## Data Sources

The module fetches:

- open interest history
- taker buy/sell volume
- top trader long/short position ratio
- premium index / mark price / latest funding rate

## Integration

- `bot.py` fetches recent flow data for each symbol before a new-entry risk
  decision.
- `flow_data.add_flow_indicators()` merges the context into the latest closed
  candle without using future flow buckets.
- Flow freshness is checked with `FLOW_MAX_AGE_MINUTES`. Stale flow columns are
  blanked and the risk layer emits `flow:stale` instead of changing position
  size.
- `risk.entry_risk_decision()` applies a small flow multiplier:
  - taker pressure aligned with the trade: modest boost
  - taker/top-trader pressure against the trade: reduction
  - extreme crowding or expensive funding: reduction
  - rising open interest aligned with candle direction: modest boost

## Backtest Policy

`FLOW_BACKTEST_ENABLED = False` by default.

Reason: using a recent-only flow dataset across a 3-year historical backtest
would create a false sense of validation. The historical engine remains driven
by OHLCV, funding history, volume profile, pattern context, calendar controls,
commission and slippage. Flow should be evaluated in testnet/paper logs until a
full historical dataset is collected.

## Risk Boundaries

The flow overlay is intentionally small:

- `FLOW_MIN_MULT = 0.85`
- `FLOW_MAX_MULT = 1.08`

It should improve trade quality without becoming an unvalidated direction
predictor.
