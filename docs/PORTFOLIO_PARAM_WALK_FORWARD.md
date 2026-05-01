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

Full run:

```bash
python portfolio_param_walk_forward.py --years 3
```

Output:

```text
portfolio_param_walk_forward_results.csv
```

## Interpretation

This result should be treated as more meaningful than a fixed-profile
walk-forward because the selected strategy parameters are chosen only from the
train segment. It still does not prove live edge by itself. The next checks are
holdout testing, slippage sensitivity, funding stress, and paper/testnet fill
review.
