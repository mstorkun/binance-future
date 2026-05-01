# Correlation Stress 2026-05-01

Status: adds a P1 correlation-stress report. This does not change live, testnet,
paper, or backtest sizing behavior.

## Why

The audit noted that current sizing is open-count based. If DOGE/LINK/TRX move
together, two open positions can behave like one larger concentrated position.

## Changes

- Added `correlation_stress.py`.
- Added ignored outputs:
  - `correlation_stress_report.json`
  - `correlation_stress_pairs.csv`
- Added unit coverage for high-correlation detection and suggested stress
  multiplier buckets.

## Usage

```bash
python correlation_stress.py --years 3
```

The report includes:

- aligned symbol return bars,
- pairwise correlations,
- maximum absolute correlation,
- average absolute correlation,
- high-correlation pairs above the threshold,
- a suggested portfolio-level risk multiplier for review.

## Important Limit

This is report-only. It deliberately does not change `risk.py` sizing yet.

If the report repeatedly shows high absolute correlations, the next step is a
side-by-side backtest of a covariance-aware cap or portfolio multiplier. The cap
should not be enabled until it improves or preserves CAGR, drawdown, walk-forward
results, and Monte Carlo tails.

## Verification

- `python -m py_compile correlation_stress.py tests\test_safety.py`
- `python -m pytest -q` -> `76 passed, 3 subtests passed`
