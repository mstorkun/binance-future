# Adaptive Futures Decision Model - 2026-05-04

Research-only report. This is not a fixed-rule indicator bot and does not
place orders. Indicators, candle structure, chart-pattern structure,
multi-timeframe context, market beta, correlation, and volatility are
converted into numeric features.
The model learns feature weights on the train slice, predicts several
future horizons, then chooses long, short, or wait after modeled costs.

Risk per trade is dynamic: predicted edge, cost, realized volatility, and
reference volatility decide the risk fraction inside configured bounds.
The multi-timeframe candle gate can block/reduce trades when weekly, daily,
4h, 1h, and trigger-candle context conflict.

Command: `python adaptive_decision_report.py --symbols DOGE/USDT:USDT --timeframe 15m --days 60 --context-timeframes 1h 4h 1d 1w --market-symbols BTC/USDT:USDT ETH/USDT:USDT --horizon-grid 12 24 36 --leverage 7 --min-risk-pct 0.01 --max-risk-pct 0.1 --target-cagr-pct 80`

## Summary

| symbol | timeframe | trades | wait_ratio_pct | total_return_pct | cagr_pct | max_dd_pct | profit_factor | sample_days | ok | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOGE/USDT:USDT | 15m | 51 | 95.92 | -41.8341 | -99.9737 | 57.8367 | 0.6825 | 23.9896 | False | target_not_met\|drawdown_limit\|profit_factor_low |

## Top Learned Weights

| horizon_bars | feature | coefficient |
| --- | --- | --- |
| 12 | ctx_4h_pattern_range_low | 1.567836 |
| 12 | ctx_1d_candle_body_atr | -1.441015 |
| 12 | ctx_1h_ema_spread_atr | 1.083412 |
| 12 | ctx_1d_pattern_slope_spread_atr | 0.956158 |
| 12 | mkt_btc_ema_spread_atr | -0.896554 |
| 12 | ctx_4h_atr_pct | -0.815382 |
| 12 | ctx_4h_ret_1 | -0.782581 |
| 12 | ctx_4h_pattern_resistance_touches | -0.727211 |
| 12 | ctx_4h_bb_width_pct | 0.68661 |
| 12 | mkt_btc_ema_fast_slope | 0.662343 |
| 12 | ctx_1d_candle_score_short | 0.636715 |
| 12 | base_pattern_range_high | -0.632322 |
| 24 | ctx_4h_pattern_range_compression | 1.55675 |
| 24 | ctx_1d_pattern_slope_spread_atr | 1.344631 |
| 24 | ctx_4h_pattern_resistance_touches | -1.15709 |
| 24 | ctx_1d_candle_body_atr | -1.079292 |
| 24 | ctx_4h_atr_pct | -1.008955 |
| 24 | ctx_4h_di_spread | 0.92211 |
| 24 | ctx_4h_pattern_range_low | 0.907565 |
| 24 | ctx_4h_ema_spread_atr | -0.869407 |
| 24 | ctx_4h_volume_z | 0.858187 |
| 24 | ctx_4h_pattern_volume_z | -0.814498 |
| 24 | ctx_1d_ema_spread_atr | -0.766753 |
| 24 | ctx_1h_di_spread | -0.723801 |
| 36 | ctx_4h_di_spread | 1.398885 |
| 36 | ctx_1d_pattern_slope_spread_atr | 1.313534 |
| 36 | ctx_4h_volume_z | 1.216241 |
| 36 | ctx_4h_pattern_range_compression | 0.981684 |
| 36 | ctx_4h_pattern_slope_spread_atr | 0.952463 |
| 36 | ctx_1d_candle_body_atr | -0.947516 |
| 36 | base_pattern_range_high | -0.945391 |
| 36 | base_ema_spread_atr | 0.907767 |
| 36 | ctx_4h_pattern_volume_z | -0.898549 |
| 36 | ctx_1h_di_spread | -0.845303 |
| 36 | base_candle_ema50_slope_pct | -0.813856 |
| 36 | ctx_4h_ret_1 | -0.799899 |

## Decision

A passing row is only a research candidate. Promotion still requires
walk-forward folds, PBO/DSR, slippage stress, liquidation checks, and real
order-flow/OI/liquidation history.
