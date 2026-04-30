# Risk Optimization - 10-Agent Review

**Date:** 2026-04-30
**Scope:** Portfolio backtest accounting, leverage/risk profile selection, and live/testnet default risk.

## Data Used

- Strategy: current hybrid regime strategy in `strategy.py`.
- Symbols: `SOL/USDT`, `ETH/USDT`, `BNB/USDT`.
- Timeframe: `4h`.
- Starting capital: `1000 USDT`.
- Portfolio engine: `portfolio_backtest.py`.
- Risk comparison output: `risk_profile_results.csv`.

## Methodology Fixes Applied Before Judgement

1. Futures account equity now uses `wallet + unrealized PnL`; locked margin is tracked separately and is not subtracted from equity.
2. Closed-position wallet update now uses net PnL including funding.
3. Portfolio sizing now mirrors the live bot: total equity is divided across watched symbols, not only open slots.
4. Calendar/news-risk gate is applied to the live bot and portfolio backtest.
5. `risk_profile_sweep.py` compares profiles without mutating `config.py`.

## Profile Results

| Profile | Leverage | Sleeve Risk | First Trade Portfolio Risk | CAGR | Max DD | Calmar |
|---|---:|---:|---:|---:|---:|---:|
| Conservative | 3x | 2.0% | 0.67% | 9.75% | 1.62% | 6.01 |
| Balanced | 5x | 3.0% | 1.00% | 15.02% | 2.71% | 5.53 |
| Aggressive | 10x | 5.0% | 1.67% | 27.51% | 5.81% | 4.73 |

These are in-sample historical results. They are useful for relative comparison, not live performance promises.

## 10-Agent Verdicts

1. **Quant/statistics:** Balanced is the best practical point; aggressive increases return but worsens risk-adjusted quality.
2. **Portfolio risk:** Conservative has the best Calmar, but balanced gives meaningfully higher CAGR while keeping drawdown low.
3. **Futures/margin:** 10x is unnecessary for the observed edge; 5x leaves more operational buffer.
4. **Slippage/microstructure:** Aggressive sizing is more sensitive to adverse fills; balanced is safer under slippage error.
5. **Funding/costs:** Cost drag is material. Higher notional profiles pay more slippage/commission; balanced keeps cost load reasonable.
6. **Drawdown psychology:** Aggressive is likely to invite manual intervention after bad streaks; balanced is easier to follow.
7. **Execution engineering:** 5x with 2 max open positions is simpler to monitor and less fragile than 10x.
8. **Regime/strategy:** Hybrid signal is not yet proven out-of-sample, so risk should not be maximized.
9. **Validation:** No live deployment until portfolio walk-forward and out-of-sample validation confirm the result.
10. **Decision control:** Default config should represent the deployable candidate, not the highest-return experiment.

## Decision

Set the default risk profile to **Balanced**:

- `LEVERAGE = 5`
- `RISK_PER_TRADE_PCT = 0.03`
- `MAX_OPEN_POSITIONS = 2`
- `DAILY_LOSS_LIMIT_PCT = 0.03`

## Next Validation Gates

1. Portfolio walk-forward using the same accounting engine.
2. Risk sweep on out-of-sample windows, not only full-history in-sample.
3. Monte Carlo on portfolio trades for balanced profile.
4. Testnet/paper only after the above gates pass.

Current status: **balanced profile selected for further validation; live trading remains NO GO.**
