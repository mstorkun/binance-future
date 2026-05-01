# Portfolio Parameter Walk-Forward

Purpose: close the methodology gap where a portfolio candidate can look strong
under one fixed parameter set but has not proven that parameter selection carries
forward out of sample.

## What It Tests

`portfolio_param_walk_forward.py` selects candidates on each train window only,
then applies the selected candidate to the next test window.

Candidate dimensions:

- Donchian entry period
- Donchian exit period
- Volume multiplier
- ATR stop multiplier
- Risk profile from `risk_profile_sweep.PROFILES`

The script does not edit `config.py` on disk and does not place orders.

## Command

Quick smoke run:

```bash
python portfolio_param_walk_forward.py --years 3 --max-param-combos 6
```

Risk-capped smoke run:

```bash
python portfolio_param_walk_forward.py --years 3 --max-param-combos 6 --risk-capped --out portfolio_param_walk_forward_risk_capped_results.csv
```

Full run:

```bash
python portfolio_param_walk_forward.py --years 3
```

Output:

```text
portfolio_param_walk_forward_results.csv
```

## Latest Smoke Result

Command:

```bash
python portfolio_param_walk_forward.py --years 3 --max-param-combos 6
```

Runtime: about 10 minutes on this Windows workstation.

Result:

| Metric | Value |
|---|---:|
| OOS periods | 7 |
| Positive OOS periods | 7/7 |
| Average OOS return | +80.04% |
| Worst OOS peak drawdown | 14.88% |
| Selected profile | `extreme_11pct` in all periods |
| Selected Donchian entry | 15 in all periods |
| Selected Donchian exit | 8 in all periods |
| Selected volume multiplier | 1.2 in all periods |
| Selected SL ATR multiplier | 1.5 or 2.0 |

Output committed:

```text
portfolio_param_walk_forward_results.csv
```

Important caveat: the selector repeatedly chose `extreme_11pct`. That means the
current scoring function still rewards aggressive leverage/risk too strongly.
Treat this as a methodology smoke pass, not as a live-trading approval.

## Latest Risk-Capped Smoke Result

Command:

```bash
python portfolio_param_walk_forward.py --years 3 --max-param-combos 6 --risk-capped --out portfolio_param_walk_forward_risk_capped_results.csv
```

Runtime: about 5.5 minutes on this Windows workstation.

Risk-capped profile universe:

```text
conservative, balanced, growth_70_compound
```

Result:

| Metric | Value |
|---|---:|
| OOS periods | 7 |
| Positive OOS periods | 7/7 |
| Average OOS return | +24.56% |
| Worst OOS peak drawdown | 6.08% |
| Selected profile | `growth_70_compound` in all periods |
| Selected Donchian entry | 15 in all periods |
| Selected Donchian exit | 8 in all periods |
| Selected volume multiplier | 1.2 in periods 1-6, 1.5 in period 7 |
| Selected SL ATR multiplier | 1.5 in periods 1-5, 2.0 in periods 6-7 |

Output committed:

```text
portfolio_param_walk_forward_risk_capped_results.csv
```

This is the more relevant smoke result than the uncapped run because it removes
the obviously over-aggressive `extreme_*` profiles from train selection.

## Interpretation

This result should be treated as more meaningful than a fixed-profile
walk-forward because the selected strategy parameters are chosen only from the
train segment. It still does not prove live edge by itself. The next checks are
holdout testing, slippage sensitivity, funding stress, and paper/testnet fill
review.

## Next Fix

Add a risk-capped selector mode before relying on this result:

- `--risk-capped` caps selectable profiles to `conservative`, `balanced`, and
  current `growth_70_compound`.
- `--profiles balanced growth_70_compound` can run an explicit custom profile
  universe.
- The remaining improvement is to report uncapped and capped selection side by
  side in one command.
