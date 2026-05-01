# Pattern Ablation 2026-05-01

Status: adds a P1 pattern-risk ablation report. This does not change live,
testnet, paper, or default backtest behavior.

## Why

The audit noted that pattern signal weights are tunable and not yet justified by
an ablation or permutation-style test.

## Changes

- Added `pattern_ablation.py`.
- Added ignored output `pattern_ablation_results.csv`.
- Added unit coverage for temporary pattern-risk toggling and summary metrics.

## Usage

```bash
python pattern_ablation.py --years 3
```

The report compares:

- `baseline_config`
- `pattern_risk_off`
- `pattern_risk_on`

Each row includes trade count, win rate, final equity, total return, CAGR,
max drawdown, Sharpe, Sortino, Calmar, commission, slippage, and funding.

## Important Limit

This is an ablation harness, not a final statistical proof. The next step is to
run it on the active portfolio and then add permutation or randomized-weight
tests if the pattern layer still appears useful.

## Verification

- `python -m py_compile pattern_ablation.py tests\test_safety.py`
- `python -m pytest -q` -> `77 passed, 3 subtests passed`
