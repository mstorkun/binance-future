# Next Steps

This file is the decision list for the current Donchian breakout + multi-symbol architecture.

## Completed

- [x] EMA crossover dropped.
- [x] Donchian breakout + volume + 1D trend filter added.
- [x] ADX and RSI filters added.
- [x] Single-symbol backtest and walk-forward updated.
- [x] Multi-symbol flat backtest added.
- [x] Multi-symbol walk-forward added.
- [x] Commission, slippage, and funding included in backtest costs.
- [x] Funding model extended to support historical data.
- [x] Monte Carlo trade-shuffle tool added.

## Current Decision

No live-money execution.

Existing evidence:

- BTC alone is weak.
- ETH/SOL/BNB are more promising.
- Multi-symbol walk-forward gives positive signal but train-test gap is high.

So the next stage is not live, but robustness testing.

## Priority 1: Parameter Stability Map

Goal: Is the result tied to a single parameter point, or does it also work on nearby parameters?

Test space:

- Donchian: 15, 18, 20, 22, 25, 30
- Volume multiplier: 1.2, 1.4, 1.5, 1.7, 2.0
- SL ATR: 1.5, 2.0, 2.5
- Symbols: ETH, SOL, BNB, BTC control

Success criteria:

- Not just a single combination, but nearby neighbors must also be positive.
- SOL/ETH results must not depend on a single over-optimized parameter.

## Priority 2: Spread Monte Carlo Results Across Symbols

Tool added and run for BTC `backtest_results.csv`.

Command:

```bash
python monte_carlo.py --trades backtest_results.csv
```

Output:

- BTC historical DD: 54.25 USDT.
- BTC Monte Carlo DD p95: 160.81 USDT.
- BTC Monte Carlo DD max: 225.16 USDT.

Interpretation: When trade order worsens, drawdown can grow roughly 3x. The same test should also be produced for ETH/SOL/BNB.

## Priority 3: Paper/Testnet

Conditions:

- At least 1-2 months.
- ETH/SOL/BNB-weighted monitoring.
- Real fill, slippage, and funding records for every order.

Required missing pieces:

- Telegram/healthcheck alarm.
- Reconnect/backoff.
- Open position and open order mismatch alarm.
- Multi-symbol `bot.py` support.

## Live Transition Rule

Only under these conditions:

- Testnet/paper results are consistent with expectations.
- Maximum DD is below the Monte Carlo limit.
- Alarm and emergency stop mechanism is working.
- Initial live capital is not 1000 USDT, but 100-200 USDT.

## Abandonment Rule

While the bot is in paper or small-live stage:

- If negative for 2 consecutive months,
- If it exceeds 2x the expected max DD,
- If it produces order/state desync,

the bot is stopped and the strategy is reevaluated.
