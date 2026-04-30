# Rolling Volume Profile

Date: 2026-05-01

## Purpose

This module turns the TradingView volume-profile idea into reproducible Binance
OHLCV logic. It is not a standalone buy/sell signal. It is a context layer that
adjusts new-entry risk based on where price sits relative to rolling value.

## Implementation

File: `volume_profile.py`

For each signal bar, the profile is built from prior bars only:

- lookback: `VOLUME_PROFILE_LOOKBACK = 120`
- minimum bars: `VOLUME_PROFILE_MIN_BARS = 60`
- bins: `VOLUME_PROFILE_BINS = 48`
- value area: `VOLUME_PROFILE_VALUE_AREA_PCT = 0.70`

Columns added by `indicators.add_indicators()`:

- `vp_poc`: point of control
- `vp_vah`: value area high
- `vp_val`: value area low
- `vp_width_pct`: value-area width as a fraction of close
- `vp_distance_to_poc_pct`: distance from close to POC
- `vp_position`: `above_value`, `inside_value`, or `below_value`

The first implementation assigns each historical bar's volume to its typical
price. This is less granular than lower-timeframe volume distribution, but it is
stable, fast, and available in both backtest and live Binance data.

## Risk Logic

File: `risk.py`

The volume profile only changes the new-entry risk multiplier:

- Long above value: modest positive multiplier.
- Short below value: modest positive multiplier.
- Inside value: small reduction because price is more mean-reverting.
- Long below value / short above value: reduction because trade direction is
  fighting the current value area.
- Near POC or very narrow value area: small reduction.

The default does not hard-block contra-value trades:

- `VOLUME_PROFILE_BLOCK_CONTRA_VALUE = False`

This keeps the feature from over-filtering valid breakouts before testnet data
confirms the behavior.

## No-Lookahead Rule

For bar `t`, the profile uses bars before `t`. If a signal is accepted on bar
`t`, backtest entry still happens on the next bar open. This avoids using future
volume distribution.

## Validation Snapshot

Source files:

- `risk_profile_results.csv`
- `portfolio_walk_forward_results.csv`
- `portfolio_monte_carlo_growth_70_compound_summary.csv`

After enabling volume profile:

- `growth_70_compound` CAGR: `80.37%`
- `growth_70_compound` peak DD: `7.67%`
- Walk-forward fixed growth periods positive: `7/7`
- Walk-forward fixed average test return: `14.63%`
- Monte Carlo bootstrap p95 peak DD: `21.41%`
- Monte Carlo bootstrap max peak DD: `70.73%`

Verdict: keep enabled for testnet, but treat it as a risk-quality layer rather
than proof that live profitability is solved.
