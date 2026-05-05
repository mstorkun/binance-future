# Adaptive Timeframe / Regime Gate Brief - 2026-05-05

Status: research-only design note. This does not enable paper, testnet, or live execution.

## Direct Answer

Yes, the bot can avoid a fixed `4h only` mindset.

The safe design is not "randomly switch timeframe". The safe design is:

1. Generate candidate signals on multiple timeframes.
2. Score the current market regime.
3. Allow only the strategy/timeframe family that historically worked in that
   regime.
4. Stay flat if no regime has evidence.

That means the bot can decide between:

- `flat / wait`
- `1h volatility breakout`
- `4h trend`
- `4h support/resistance reversion`
- future families such as liquidation or stat-arb

But every regime permission must be trained and tested out-of-sample. Otherwise
it becomes curve-fitting.

## Current Diagnostic

`docs/VOLATILITY_BREAKOUT_REGIME_DIAGNOSTICS_2026_05_05.md` checked the
Volatility Breakout V1 folds against:

- BTC return regime
- BTC 24h/72h/168h realized volatility
- BTC 1h EMA50/200 side
- BTC 4h EMA21/55 side
- BTC 4h ADX
- BTC squeeze state
- BTC shock frequency
- BTC funding level

Important correction:

- Claude's suggested `2,5,10,12` fold set does not match the current strict V1
  artifact.
- Current baseline-positive folds are `6,7,8,11,12`.
- Current severe-positive folds are only `6`.

That means severe-positive evidence is too small to convert directly into a
live/paper rule.

## What The Diagnostic Suggests

The baseline-positive folds were not high-volatility moonshot periods. They
looked more like controlled BTC regimes:

- BTC 72h vol was slightly lower than losing folds.
- BTC 4h ADX was lower than losing folds.
- BTC directional side was more balanced.
- Funding did not clearly explain the difference.

This is useful, but not strong enough yet.

## V2 Research Hypothesis

The next valid experiment is a regime-permission overlay:

- Keep Volatility Breakout V1 signals unchanged.
- Add a grid of BTC regime gates:
  - BTC 72h vol band.
  - BTC 4h ADX max.
  - BTC shock frequency max.
  - BTC funding abs max.
  - Optional BTC side mode: aligned, neutral-allowed, or short-regime-only.
- Re-run full walk-forward.
- Do not promote unless the strict gate improves out-of-sample.

## Live Behavior Rule

If a regime gate eventually passes, live behavior should be:

- If regime is valid: allow the relevant timeframe strategy.
- If regime is invalid: stay flat.
- If data is stale or missing: stay flat.
- If news/macro/event policy says observe: stay flat.

This matches the user's requirement: the bot should not force trades, should
wait when conditions are bad, and should not pay unnecessary commissions.

