# Growth 70 Validation

Date: 2026-05-01

The target is not a profit cap. `70%/yr` is a validation gate. If a strong
trend year produces more, the bot should let winners run through trailing exits.

## Selected Candidate

`growth_70_compound`

- `LEVERAGE = 10`
- `RISK_BASIS = "portfolio"`
- `RISK_PER_TRADE_PCT = 0.04`
- `MAX_OPEN_POSITIONS = 2`
- Rolling volume-profile risk context enabled.
- Candle-pattern context enabled as align-only risk boost:
  - aligned pattern: modest risk increase
  - opposing pattern: no penalty by default
- Futures flow context is wired for live/testnet risk decisions, but disabled
  for long historical backtests because Binance exposes most flow endpoints as
  recent-window data.
- Correlation-aware second-entry sizing enabled:
  - first open position: 4.00% base risk
  - second open position: 2.68% base risk
  - third would be 2.00%, but max open positions is 2
- Daily loss stop: 6%

This uses current equity, so if 1000 USDT grows to 1500 USDT, sizing is based on
1500 USDT.

## In-Sample Portfolio Backtest

Source: `risk_profile_results.csv`, corrected portfolio engine.

| Profile | Risk basis | Risk | Leverage | CAGR | Peak DD | Comment |
|---|---|---:|---:|---:|---:|---|
| conservative | portfolio | 2% | 3x | 34.37% | 3.87% | Safer, below target |
| balanced | portfolio | 3% | 5x | 55.42% | 5.78% | Strong, below target |
| growth_70_compound | portfolio | 4% | 10x | 79.54% | 7.67% | Selected candidate |
| growth_100_compound | portfolio | 5% | 10x | 107.11% | 9.55% | Higher return, weaker risk quality |
| extreme_10pct | portfolio | 10% | 10x | 305.20% | 16.42% | Too aggressive for default |
| extreme_11pct | portfolio | 11% | 10x | 351.73% | 18.02% | Too aggressive for default |

## Portfolio Walk-Forward

Source: `portfolio_walk_forward_results.csv`.

Fixed `growth_70_compound` profile:

- Positive test periods: 7/7
- Average test-period return: 14.34%
- Worst test-period peak DD: 7.67%

This supports the candidate better than the previous sleeve-based sizing, but it
is still only historical validation.

## Monte Carlo

Source: `portfolio_monte_carlo_growth_70_compound_summary.csv`.

| Method | Ending p05 | Ending p50 | Peak DD p95 | Peak DD max | Loss probability |
|---|---:|---:|---:|---:|---:|
| shuffle | 5807.31 | 5807.31 | 7.82% | 12.48% | 0.0% |
| bootstrap | 4104.69 | 5760.24 | 8.69% | 20.81% | 0.0% |
| block bootstrap | 4103.38 | 5741.22 | 7.16% | 12.57% | 0.0% |

Interpretation:

- The target is plausible in historical tests.
- The tail risk is not zero. Bootstrap can create very deep path drawdowns.
- `10-11%` portfolio risk is not the default; it creates impressive in-sample
  returns but the path risk is too large.

## Verdict

`growth_70_compound` is the current testnet candidate.

Live trading remains gated by:

1. Testnet/paper run with real fills and order-book guard logs.
2. Lookahead/recursive methodology checks.
3. News/event watcher running in reduce/block mode only.
4. Manual review after at least 30-50 testnet trades.
