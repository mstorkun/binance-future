# PBO Matrix Harness 2026-05-01

Status: adds the missing full candidate-by-fold matrix path needed for a real
PBO-style analysis. The first full run is recorded in
[PBO_FULL_RESULT_2026_05_02.md](PBO_FULL_RESULT_2026_05_02.md).

## Why

The earlier overfit report used selected walk-forward rows only. That is useful
as a conservative warning, but true PBO analysis needs every candidate's
train-side and out-of-sample performance for each fold.

## Change

- `portfolio_param_walk_forward.py` now accepts `--matrix-out`.
- When `--matrix-out` is provided, every candidate is also evaluated on the test
  slice for that fold and written to a candidate-by-fold matrix CSV.
- `pbo_report.py` reads that matrix and reports:
  - selected candidate per fold,
  - selected candidate OOS rank,
  - OOS rank percentile,
  - logit OOS rank,
  - PBO hit rate.
- Runtime outputs are ignored by git:
  - `portfolio_param_candidate_matrix.csv`
  - `pbo_report.json`

## Full Run Command

This is intentionally expensive because it tests every candidate in every fold:

```bash
python portfolio_param_walk_forward.py --years 3 --train-bars 3000 --test-bars 500 --roll-bars 500 --risk-capped --matrix-out portfolio_param_candidate_matrix.csv
python pbo_report.py --matrix portfolio_param_candidate_matrix.csv --out pbo_report.json
```

Use a smaller smoke first:

```bash
python portfolio_param_walk_forward.py --years 1 --train-bars 700 --test-bars 200 --roll-bars 200 --risk-capped --max-param-combos 1 --out pbo_smoke_wf.csv --matrix-out pbo_smoke_matrix.csv
python pbo_report.py --matrix pbo_smoke_matrix.csv --out pbo_smoke_report.json
```

## Interpretation

This commit adds the harness, not the final full PBO result. The full run should
be treated as a methodology job, not as a live-trading gate that can be skipped.

## Verification

- `python -m py_compile portfolio_param_walk_forward.py pbo_report.py tests\test_safety.py`
- `python -m pytest tests\test_safety.py -q` -> `87 passed, 3 subtests passed`
- `python -m pytest -q` -> `87 passed, 3 subtests passed`
