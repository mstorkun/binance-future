# Overfit Controls 2026-05-01

Status: closes the current P1 "DSR/PBO or equivalent conservative overfit
controls" item with conservative proxy metrics.

Update 2026-05-02: the full candidate-by-fold matrix run is now recorded in
[PBO_FULL_RESULT_2026_05_02.md](PBO_FULL_RESULT_2026_05_02.md). That full run is
stronger evidence than the selected-row proxy below.

## Why

The candidate portfolio was selected from many symbol combinations and later
parameter/risk-profile choices. Raw CAGR, Calmar, and Sharpe are not enough when
the best result may be a multiple-testing winner.

## Change

- `risk_metrics.multiple_testing_sharpe_haircut()` adds a Bonferroni-adjusted
  Sharpe haircut.
- `risk_metrics.walk_forward_overfit_summary()` adds a train/test degradation
  and PBO-style proxy from existing walk-forward results.
- `risk_adjusted_report.py` now includes an `overfit_controls` section and reads
  `portfolio_param_walk_forward_results.csv` by default.

These are deliberately labelled as proxies, not full academic DSR/PBO. A full
PBO implementation still needs the complete candidate-by-fold matrix, not only
the selected candidate per fold.

## Current Report

Command:

```bash
python risk_adjusted_report.py
```

Key output:

| Metric | Value |
|---|---:|
| Nominal Sharpe | 3.6935 |
| Candidate sweep tests | 455 |
| Bonferroni alpha | 0.00010989 |
| Sharpe haircut | 5.9978 |
| Deflated Sharpe proxy | -2.3043 |
| Passes zero-edge after haircut | false |
| Walk-forward folds | 7 |
| Positive test folds | 7 |
| Severe degradation folds | 7 |
| PBO proxy | 1.0 |

## Interpretation

This does not prove the strategy has no edge. It says the current evidence is
not strong enough after penalizing the amount of search. Live trading remains
blocked, and further strategy claims should be based on holdout and full
candidate-matrix PBO rather than the best historical run.

The later full candidate-matrix PBO result improved this specific overfit
concern: PBO `0.1429`, selected candidates OOS top-half in `6/7` folds. Live
trading still remains blocked by execution, fill-quality, and stream-readiness
gates.

## Verification

- `python -m py_compile risk_metrics.py risk_adjusted_report.py tests\test_safety.py`
- `python -m pytest tests\test_safety.py -q` -> `85 passed, 3 subtests passed`
- `python risk_adjusted_report.py`
