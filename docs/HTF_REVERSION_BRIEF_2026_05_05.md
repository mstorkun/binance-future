# HTF Support/Resistance Reversion Brief - 2026-05-05

Status: research-only candidate. This does not enable paper, testnet, or live execution.

## Why This Candidate Exists

Hurst-MTF V3 improved cost robustness but still failed strict gates and its
own diagnostic selected `LEAVE_HURST_MTF_FAMILY`. The next candidate therefore
switches away from trend-following and tests a separate mean-reversion family.

This candidate asks a simple question:

- When price reaches a prior 4h support or resistance area,
- and the move looks exhausted by RSI,
- and ADX says the market is not in a strong directional trend,
- can a controlled reversal trade survive realistic Binance Futures costs?

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

- 1h Binance Futures OHLCV, resampled to 4h and 1d.
- Prior 4h support/resistance levels over 60, 120, and 180 bars.
- 4h ATR, RSI, ADX, and volume z-score.
- 1d EMA200 trend side used only to avoid trading directly against the larger trend.

Entry logic:

- Long: previous closed 4h candle touched or swept prior support, then closed
  back above that support while RSI is low and ADX is capped.
- Short: previous closed 4h candle touched or swept prior resistance, then
  closed back below that resistance while RSI is high and ADX is capped.
- Entry happens on the next 4h open, so the signal uses only closed data.

Risk/exit logic:

- Vol-targeted sizing with 10x leverage cap, max 20% equity margin per position,
  and max 4 concurrent positions.
- Hard stop beyond the swept support/resistance by ATR.
- Take profit at the nearer of an ATR target or the opposite range side.
- Time stop after 12 bars.

## Strict Gate

Same gate as prior candidates. A pass requires every check true:

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

If this candidate fails, it stays `benchmark_only`. Do not connect it to
paper/live behavior unless every strict gate passes first.

