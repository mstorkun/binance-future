# TradingView Indicator Research

Date: 2026-05-01

Source pages:

- https://tr.tradingview.com/ideas/indicators/
- https://tr.tradingview.com/scripts/blocks/
- https://tr.tradingview.com/scripts/volumes/
- https://tr.tradingview.com/scripts/search/supertrend/
- https://tr.tradingview.com/script/P2XgvcKM-Aggregated-Volume-Profile-Spot-Futures/

## Useful For This Bot

### 1. Liquidity / Order Blocks / BOS-CHoCH / FVG

TradingView community scripts around liquidity/order blocks commonly combine:

- BOS / CHoCH market structure
- confirmed swing highs/lows
- liquidity pools above equal highs and below equal lows
- liquidity sweeps
- order blocks
- fair value gaps
- ATR-sized zones
- volume-weighted intensity

Why useful:

- Directly matches our whale-wick concern.
- Can help avoid entering exactly into nearby liquidity pools.
- Can improve stop placement by separating real structure break from wick sweep.

Implementation rule:

- Use confirmed pivots only.
- No repainting.
- Do not use as standalone signal.
- First integration should be a risk/filter layer:
  - reduce risk if entry is too close to opposing liquidity,
  - skip trailing update on sweep candles,
  - allow breakout only after close-confirmed BOS.

Candidate module:

- `market_structure.py`

### 2. Volume Profile / POC / VAH / VAL

Several scripts emphasize volume profile:

- Point of Control (POC)
- Value Area High / Low
- high-volume nodes
- low-volume nodes
- volume distribution across price bins
- spot + futures aggregated volume

Why useful:

- Helps distinguish trend continuation from range/mean-reversion.
- Price inside value area often behaves more mean-reverting.
- Breakout above VAH / below VAL with volume can strengthen trend entries.
- POC can act as a magnet; entering breakout toward a nearby POC may be lower quality.

Implementation rule:

- Build a rolling profile from Binance OHLCV first.
- Later improve with lower-timeframe or trade data.
- Use POC/VAH/VAL as context/risk multiplier before using as signal.

Implemented module:

- `volume_profile.py`

Implementation status:

- Rolling POC / VAH / VAL is now generated from Binance OHLCV.
- The profile uses prior bars only and affects risk sizing, not signal direction.
- Validation stayed positive after enabling it; see `docs/VOLUME_PROFILE.md`.

### 3. Multi-Timeframe Supertrend

TradingView Supertrend scripts use ATR-based trend direction across multiple
timeframes.

Why useful:

- It is simple, non-subjective, and compatible with Binance OHLCV.
- Can cross-check current Donchian/daily EMA trend filter.
- Can provide an alternative trailing-stop line during strong trends.

Implementation rule:

- Add as confirmation first.
- Do not replace Donchian until walk-forward proves improvement.
- Compare H4 + 1D Supertrend agreement against current `daily_trend`.

Candidate module:

- extend `indicators.py` with `supertrend`.

### 4. VSA / Effort vs Result / Volume Delta Proxy

TradingView volume scripts include ideas such as:

- effort = volume/range activity
- result = actual price displacement
- no demand / no supply
- upthrust / shakeout / stopping volume
- volume delta approximations

Why useful:

- Helps identify fake breakout candles.
- Useful for whale wick protection: huge volume but poor close-through can mean absorption.
- Can improve `execution_guard.is_spike_bar()`.

Implementation rule:

- Start with OHLCV proxy.
- Later use Binance raw klines or trade stream for taker-buy/taker-sell volume.

Candidate module:

- extend `execution_guard.py` or add `volume_quality.py`.

## Lower Priority / Avoid

### Elliott Wave

Useful for manual analysts, but too subjective for this bot. Hard to validate
without curve-fitting and manual relabeling.

### Generic support/resistance ideas

TradingView idea posts often include discretionary levels, targets and stops.
They are useful as human context but not reproducible enough for the bot.

### Invite-only or black-box indicators

Do not depend on these. If source and exact logic are unavailable, they cannot be
validated or reproduced in walk-forward.

### TradingView-only data

Avoid logic that requires TradingView-only feeds unless we can obtain the same
data from Binance or another API. Otherwise backtest/live mismatch appears.

## Recommended Implementation Order

1. Add rolling `volume_profile.py`:
   - POC
   - VAH / VAL
   - price location: below value, inside value, above value
   - breakout context multiplier
2. Add `market_structure.py`:
   - confirmed pivots
   - BOS / CHoCH
   - equal high/low liquidity
   - sweep detection
3. Extend `execution_guard.py`:
   - use liquidity sweep and VSA-style effort/result to avoid fake SL/trailing moves
4. Add Supertrend only as an A/B test against current trend filter.

## Validation Rule

Every new indicator must pass:

1. portfolio backtest,
2. portfolio walk-forward,
3. bootstrap and block Monte Carlo,
4. no-lookahead review,
5. testnet logs with real fills.

If CAGR improves but peak drawdown or Monte Carlo tail risk worsens materially,
the indicator is rejected or used only as a risk reducer.
