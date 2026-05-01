# Risk-Adjusted Metrics 2026-05-01

Status: closes the P1 reporting gap for missing Sharpe/Sortino and basic
multiple-testing visibility. This does not approve live trading.

## Changes

- Added `risk_metrics.py`.
- Added `risk_adjusted_report.py`.
- Added overfit-control proxies in
  [OVERFIT_CONTROLS_2026_05_01.md](OVERFIT_CONTROLS_2026_05_01.md).
- `portfolio_candidate_sweep.py` now adds:
  - annualized volatility,
  - Sharpe,
  - Sortino,
  - Calmar.
- Candidate sweep output now prints a multiple-testing summary:
  - number of tested combinations,
  - best metric and best symbol set,
  - Bonferroni-adjusted 5% alpha.

## Usage

```bash
python portfolio_candidate_sweep.py --years 3 --min-size 3 --max-size 3 --top 30
python risk_adjusted_report.py --equity portfolio_equity.csv --sweep portfolio_candidate_sweep_results.csv --walk-forward portfolio_param_walk_forward_results.csv
```

`risk_adjusted_report.py` writes ignored `risk_adjusted_report.json`.

## Interpretation

These metrics make the report harder to overstate, but they are not proof of
edge by themselves:

- Sharpe/Sortino depend on the bar-level equity path and can still be inflated
  by overfit symbol selection.
- Bonferroni alpha and the Sharpe haircut expose the cost of testing many
  portfolios, but they are still conservative proxies rather than full academic
  DSR.
- The PBO-style proxy uses selected walk-forward rows only. A full PBO still
  needs the complete candidate-by-fold matrix.

## Verification

- `python -m py_compile risk_metrics.py risk_adjusted_report.py portfolio_candidate_sweep.py tests\test_safety.py`
- `python -m pytest -q` -> `85 passed, 3 subtests passed`
