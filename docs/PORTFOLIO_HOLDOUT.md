# Portfolio Holdout

Purpose: reserve the final bars as a single untouched holdout window, select
parameters only on the pre-holdout train range, then evaluate the selected
candidate on the holdout.

This is a research-only check. It does not change `config.py` on disk and does
not place orders.

## Command

Risk-capped smoke:

```bash
python portfolio_holdout.py --years 3 --holdout-bars 500 --max-param-combos 6 --out portfolio_holdout_results.csv
```

Full risk-capped run:

```bash
python portfolio_holdout.py --years 3 --holdout-bars 500
```

## Output

```text
portfolio_holdout_results.csv
```

## Interpretation

This check is stricter than reading the last walk-forward fold casually because
the holdout boundary is explicit: all train selection happens before the final
500 bars, then the selected candidate is replayed only on that final segment.

It still does not prove live readiness. Passing holdout means the current
research candidate deserves more paper/testnet observation, not live capital.

## Latest Smoke Result

Command:

```bash
python portfolio_holdout.py --years 3 --holdout-bars 500 --max-param-combos 6 --out portfolio_holdout_results.csv
```

Result:

| Metric | Value |
|---|---:|
| Train range | 2023-05-13 20:00:00 -> 2026-02-07 00:00:00 |
| Holdout range | 2026-02-07 04:00:00 -> 2026-05-01 08:00:00 |
| Train bars | 6002 |
| Holdout bars | 500 |
| Candidate count | 18 |
| Selected profile | `growth_70_compound` |
| Selected params | `D15 / DX8 / VOL1.2 / SL2.0` |
| Train return | +2363.00% |
| Train peak DD | 5.13% |
| Holdout trades | 30 |
| Holdout win rate | 70.00% |
| Holdout return | +10.55% |
| Holdout peak DD | 5.76% |

Output committed:

```text
portfolio_holdout_results.csv
```

Conclusion: the final 500-bar holdout stays positive under the same risk-capped
smoke selector. This supports continued paper/testnet observation, not live
approval.
