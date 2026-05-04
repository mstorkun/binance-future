# Hurst MTF Momentum Phase A Report - 2026-05-04

Status: `incomplete_timeout`

This is a documentation-only Phase A status draft. It does not report a completed
strict-gate result, does not approve Phase B, and does not enable paper, testnet,
or live execution.

The full strict run has timed out before producing a trustworthy complete result.
No live result, strict pass, or performance metric should be inferred from this
file. The next step is an optimized rerun of the same strict validation without
weakening any gate.

## Phase A Implementation Status

Observed Phase A research modules are present in the working tree:

| Module | Phase A role | Status |
|---|---|---|
| `hurst_gate.py` | Rolling DFA / R/S Hurst regime layer and bias-audit row | Implemented in working tree |
| `mtf_momentum_signal.py` | Closed-bar 1d trend, 4h structure/Hurst, and 1h trigger signal frame | Implemented in working tree |
| `vol_target_sizing.py` | Deterministic volatility-target position notional helpers | Implemented in working tree |
| `hurst_mtf_momentum_report.py` | Research-only walk-forward, PBO matrix, cost-stress, attribution, and strict summary harness | Implemented in working tree |
| `tests/test_hurst_mtf_momentum.py` | Unit coverage for Hurst separation, closed-bar signal behavior, sizing cap, and fixed candidate grid | Implemented in working tree |

Scope note: these files are not wired into paper, testnet, or live execution by
this report. This documentation pass intentionally did not change code.

## Timeout Status

The strict run is not complete. Because the full run timed out, the following
items remain unknown and must not be filled from partial output:

| Item | Current status |
|---|---|
| Full 12-fold strict walk-forward | Unknown, timed out |
| Severe-cost CAGR | Unknown |
| Full PBO matrix result | Unknown |
| DSR proxy after Bonferroni haircut | Unknown |
| Sortino ratio | Unknown |
| Per-symbol PnL concentration | Unknown |
| Per-month PnL concentration | Unknown |
| Tail-capture profile | Unknown |
| Crisis-alpha result | Unknown |
| Total walk-forward trade sample | Unknown |

Decision: Phase B remains blocked until a completed strict run proves every gate.

## Strict Gates From Brief

The brief gates are reproduced here without relaxing any threshold:

| Gate | Threshold | Current evidence |
|---|---|---|
| Net CAGR after severe cost stress | >= 80% | Unknown - timeout |
| PBO (full matrix) | < 0.3 | Unknown - timeout |
| Walk-forward positive fold ratio | >= 7/12 | Unknown - timeout |
| DSR proxy after Bonferroni haircut | >= 0 | Unknown - timeout |
| Sortino ratio | >= 2.0 (downside vol focus, not Sharpe) | Unknown - timeout |
| Per-symbol PnL concentration | no symbol > 40% | Unknown - timeout |
| Per-month PnL concentration | no month > 25% | Unknown - timeout |
| Tail capture | top 5% of trades produce 50-80% of PnL (convex profile check) | Unknown - timeout |
| Crisis alpha | net positive on 2024-08-05, 2025-10-10 cascade days | Unknown - timeout |
| Sample size | >= 200 trades total across walk-forward | Unknown - timeout |

The implementation-plan strict pass gate also remains unchanged:

`net CAGR >= 80% after severe-cost scenario AND PBO < 0.3 AND >= 7/12 fold positive AND DSR proxy >= 0`.

## Required Optimized Rerun

Run the same strict validation with an execution plan that avoids timeout, but do
not reduce the gate thresholds, candidate validity requirements, cost stress, or
fold standards.

Baseline strict rerun command:

```powershell
python hurst_mtf_momentum_report.py --years 3 --folds 12 --train-bars 2400 --test-bars 300 --out hurst_mtf_momentum_results.csv --matrix-out hurst_mtf_momentum_pbo_matrix.csv --trades-out hurst_mtf_momentum_trades.csv --json-out hurst_mtf_momentum_report.json --md-out docs/HURST_MTF_MOMENTUM_REPORT_2026_05_04.md
```

Optimization work should target runtime only:

- Cache fetched 1h OHLCV per symbol before candidate/fold evaluation.
- Reuse prepared 1d/4h/1h signal frames across candidates.
- Keep the fixed first-pass universe and the full candidate grid unless the
  brief is explicitly changed by the user.
- Preserve all cost scenarios, including severe `60bps` slippage and `2x`
  funding.
- Preserve the full PBO matrix and attribution checks.

Only after the optimized rerun completes should this report be replaced with the
generated strict result. If any strict gate fails, status must remain
`benchmark_only` or another explicit no-go state, not Phase B approval.

## Current Decision

Phase A implementation appears present, but validation is incomplete because the
full strict run timed out. Phase B, paper deployment, testnet, and live trading
remain blocked.
