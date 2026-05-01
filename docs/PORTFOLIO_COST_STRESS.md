# Portfolio Cost Stress

Purpose: replay the already-selected risk-capped walk-forward folds under
harsher execution-cost assumptions.

This is different from re-optimizing parameters. The script reads
`portfolio_param_walk_forward_risk_capped_results.csv`, keeps each fold's
selected profile and strategy parameters fixed, and reruns only the OOS test
segments with stressed fees, slippage, and funding cost.

## Command

```bash
python portfolio_cost_stress.py --wf-results portfolio_param_walk_forward_risk_capped_results.csv --years 3
```

Outputs:

```text
portfolio_cost_stress_results.csv
portfolio_cost_stress_folds.csv
```

## Scenarios

| Scenario | Fee | Slippage | Funding Cost |
|---|---:|---:|---:|
| `baseline` | 1x | 1x | 1x |
| `slippage_2x` | 1x | 2x | 1x |
| `slippage_3x` | 1x | 3x | 1x |
| `funding_cost_2x` | 1x | 1x | 2x adverse |
| `fee_slippage_2x` | 2x | 2x | 1x |
| `severe_costs` | 2x | 3x | 2x adverse |

Funding stress is adverse: positive funding costs are multiplied, while funding
income is reduced.

## Interpretation

This test answers whether the current risk-capped OOS evidence survives harsher
cost assumptions. It does not model every live-trading hazard; orderbook depth,
partial fills, outages, and liquidation gaps still require testnet/paper
execution evidence.

## Latest Result

Command:

```bash
python portfolio_cost_stress.py --wf-results portfolio_param_walk_forward_risk_capped_results.csv --years 3
```

Result:

| Scenario | Positive OOS | Avg OOS Return | Worst OOS Return | Worst Peak DD | Compounded OOS Return |
|---|---:|---:|---:|---:|---:|
| `baseline` | 7/7 | +24.56% | +5.42% | 6.08% | +345.36% |
| `slippage_2x` | 7/7 | +16.50% | +0.64% | 7.88% | +178.81% |
| `slippage_3x` | 5/7 | +8.14% | -8.14% | 12.38% | +63.92% |
| `funding_cost_2x` | 7/7 | +24.09% | +5.23% | 6.10% | +333.52% |
| `fee_slippage_2x` | 5/7 | +12.19% | -4.78% | 11.36% | +113.32% |
| `severe_costs` | 4/7 | +4.40% | -11.28% | 14.58% | +28.25% |

Outputs committed:

```text
portfolio_cost_stress_results.csv
portfolio_cost_stress_folds.csv
```

Conclusion: the risk-capped OOS result survives 2x slippage cleanly. At 3x
slippage or combined fee/slippage stress, some OOS folds turn negative but the
compounded OOS path remains positive. The severe scenario is still positive but
weak enough that live deployment remains blocked.
