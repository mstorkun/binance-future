# Urgent Exit Policy - 2026-05-04

Status: research/paper/testnet safety policy. This does not approve live
trading.

User requirement:

- The bot should not churn on small moves.
- If a long/short goes into loss, it may wait when the full thesis is still
  valid.
- Around `30%` account-level adverse loss can be tolerated only when market,
  broad timeframe trend, news/event context, and indicator/candle context still
  support the trade; this is not a fixed stop.
- `50%` account-level adverse loss is an absolute cap to avoid liquidation-style
  ruin.
- When real urgent exit is required, commission is secondary and the bot should
  use a reduce-only market close.

## Implemented

Added `urgent_exit_policy.py`.

The decision is thesis-aware:

1. It first calculates adverse loss in R and account-equity percent.
2. It checks whether the original thesis is invalidated by daily/weekly trend,
   Donchian exit, EMA stack, and strong adverse trend context.
3. It does not market-close only because a trade is red.
4. It market-closes when:
   - absolute adverse account loss reaches `URGENT_EXIT_ABSOLUTE_EQUITY_LOSS_PCT`
     (`50%` default),
   - adverse loss reaches the soft max zone and the thesis is invalid,
   - adverse loss reaches the soft max zone and the broader context no longer
     supports holding,
   - adverse momentum plus thesis invalidation confirms urgent risk,
   - liquidation buffer gets too tight.

`bot.py`, `paper_runner.py`, and passive `trade_executor.py` now use this policy.
Soft stop hits can be held when `THESIS_HOLD_SOFT_STOP_ENABLED=True` and the
urgent policy says the thesis remains valid. Hard stop, liquidation, and urgent
market exit stay fail-safe.

Existing live/testnet market close path is `order_manager.close_position_market()`.
It submits a `reduceOnly=True` market order and keeps existing protection if the
close fails or only partially fills.

## Default Parameters

| Config | Default | Meaning |
|---|---:|---|
| `THESIS_HOLD_SOFT_STOP_ENABLED` | `True` | Soft stop can be advisory when thesis is valid |
| `URGENT_EXIT_MIN_LOSS_R` | `1.50` | Start evaluating urgent loss only after meaningful adverse R |
| `URGENT_EXIT_MIN_EQUITY_LOSS_PCT` | `8.00` | Start evaluating urgent loss only after meaningful account impact |
| `URGENT_EXIT_MAX_EQUITY_LOSS_PCT` | `30.00` | Thesis-invalid large-loss zone |
| `URGENT_EXIT_ABSOLUTE_EQUITY_LOSS_PCT` | `50.00` | Hard account-level emergency cap |
| `URGENT_EXIT_HOLD_SUPPORT_MIN_REASONS` | `2` | Minimum supporting context reasons for large-loss hold |
| `URGENT_EXIT_LIQUIDATION_BUFFER_PCT` | `0.03` | Exit before liquidation buffer gets too tight |

## Decision Rule

Normal loss:

`hold / continue evaluating`

Large loss around 30%, with market/trend/news/indicator context still supportive:

`hold, no market close`

Large loss around 30%, with thesis invalid or support gone:

`reduceOnly market close`

Any loss near absolute `50%` cap:

`reduceOnly market close`

Liquidation buffer too tight:

`reduceOnly market close`

## Source

Binance USD-M Futures new-order API supports market orders and `reduceOnly`
parameters for one-way position mode:
https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order
