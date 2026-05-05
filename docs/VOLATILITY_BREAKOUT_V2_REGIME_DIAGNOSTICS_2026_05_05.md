# Volatility Breakout Regime Diagnostics - 2026-05-05

Status: diagnostic-only. This does not enable paper, testnet, or live execution.

## Fold Sets

- Current baseline-positive folds: `[1, 5, 6, 8, 10, 11, 12]`
- Current severe-positive folds: `[5, 6, 10, 11]`
- Claude-claimed folds checked separately: `[2, 5, 10, 12]`

## Fold Regime Rows

| period | baseline_return_pct | severe_return_pct | baseline_positive | severe_positive | claude_fold | btc_return_pct | btc_vol_72h_mean | btc_h4_adx_mean | btc_h4_long_share | btc_h4_short_share | btc_funding_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.4898 | -0.8435 | True | False | False | -5.3859 | 0.4404 | 27.9794 | 0.34 | 0.66 | 0.0001 |
| 2 | 0.0 | 0.0 | False | False | True | -9.2671 | 0.571 | 28.3322 | 0.33 | 0.67 | 0.0 |
| 3 | -5.7237 | -9.3212 | False | False | False | 27.1315 | 0.3981 | 33.5072 | 0.74 | 0.26 | 0.0001 |
| 4 | -2.4377 | -3.8215 | False | False | False | 23.9533 | 0.5476 | 28.8007 | 0.8333 | 0.1667 | 0.0001 |
| 5 | 2.2993 | 1.079 | True | True | True | 3.1188 | 0.4981 | 22.2105 | 0.4133 | 0.5867 | 0.0001 |
| 6 | 2.755 | 1.6874 | True | True | False | -18.3856 | 0.5255 | 24.413 | 0.2233 | 0.7767 | 0.0 |
| 7 | -9.2676 | -13.4094 | False | False | False | 38.3424 | 0.4275 | 29.829 | 0.89 | 0.11 | 0.0 |
| 8 | 0.6391 | -2.2751 | True | False | False | 6.2815 | 0.3088 | 24.4993 | 0.58 | 0.42 | 0.0 |
| 9 | -1.3735 | -8.0873 | False | False | False | -3.6682 | 0.317 | 24.267 | 0.4867 | 0.5133 | 0.0001 |
| 10 | 7.2665 | 2.8272 | True | True | True | -1.8089 | 0.3302 | 34.175 | 0.5233 | 0.4767 | 0.0 |
| 11 | 5.5747 | 2.061 | True | True | False | -17.6511 | 0.4763 | 27.8551 | 0.3267 | 0.6733 | 0.0 |
| 12 | 1.6822 | -1.0618 | True | False | True | -13.8111 | 0.3631 | 24.1641 | 0.43 | 0.57 | 0.0001 |

## Group Means

| group | folds | btc_return_pct | btc_vol_72h_mean | btc_h4_adx_mean | btc_h4_long_share | btc_h4_short_share | btc_funding_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_positive | 7 | -6.806 | 0.4203 | 26.4709 | 0.4052 | 0.5948 | 0.0 |
| severe_positive | 4 | -8.6817 | 0.4575 | 27.1634 | 0.3717 | 0.6283 | 0.0 |
| claude_claimed | 4 | -5.4421 | 0.4406 | 27.2204 | 0.4242 | 0.5758 | 0.0 |

## Severe-Positive Differentials

| metric | selected_mean | other_mean | delta |
| --- | --- | --- | --- |
| btc_return_pct | -8.6817 | 7.9471 | -16.6287 |
| btc_vol_24h_mean | 0.4366 | 0.4051 | 0.0314 |
| btc_vol_72h_mean | 0.4575 | 0.4217 | 0.0358 |
| btc_vol_168h_mean | 0.4653 | 0.4302 | 0.0351 |
| btc_side_long_share | 0.161 | 0.2402 | -0.0792 |
| btc_side_short_share | 0.2279 | 0.1632 | 0.0647 |
| btc_h4_long_share | 0.3717 | 0.5787 | -0.2071 |
| btc_h4_short_share | 0.6283 | 0.4213 | 0.2071 |
| btc_h4_adx_mean | 27.1634 | 27.6724 | -0.509 |
| btc_sq120_mean | 0.2252 | 0.2229 | 0.0024 |
| btc_sq240_mean | 0.2334 | 0.2334 | 0.0 |
| btc_volume_z_mean | 0.0273 | 0.0304 | -0.0031 |
| btc_abs_shock_gt2_share | 0.0612 | 0.0626 | -0.0014 |
| btc_abs_shock_gt3_share | 0.0194 | 0.0227 | -0.0033 |
| btc_funding_mean | 0.0 | 0.0001 | -0.0 |
| btc_funding_abs_mean | 0.0001 | 0.0001 | -0.0 |
| btc_funding_positive_share | 0.855 | 0.8867 | -0.0317 |

## Baseline-Positive Differentials

| metric | selected_mean | other_mean | delta |
| --- | --- | --- | --- |
| btc_return_pct | -6.806 | 15.2984 | -22.1044 |
| btc_vol_24h_mean | 0.4022 | 0.4344 | -0.0322 |
| btc_vol_72h_mean | 0.4203 | 0.4523 | -0.0319 |
| btc_vol_168h_mean | 0.428 | 0.4614 | -0.0334 |
| btc_side_long_share | 0.1696 | 0.2757 | -0.106 |
| btc_side_short_share | 0.2263 | 0.1267 | 0.0996 |
| btc_h4_long_share | 0.4052 | 0.656 | -0.2508 |
| btc_h4_short_share | 0.5948 | 0.344 | 0.2508 |
| btc_h4_adx_mean | 26.4709 | 28.9472 | -2.4763 |
| btc_sq120_mean | 0.2234 | 0.224 | -0.0006 |
| btc_sq240_mean | 0.2315 | 0.2361 | -0.0045 |
| btc_volume_z_mean | 0.0339 | 0.0229 | 0.0109 |
| btc_abs_shock_gt2_share | 0.0632 | 0.0607 | 0.0025 |
| btc_abs_shock_gt3_share | 0.0215 | 0.0217 | -0.0001 |
| btc_funding_mean | 0.0 | 0.0001 | -0.0 |
| btc_funding_abs_mean | 0.0001 | 0.0001 | -0.0 |
| btc_funding_positive_share | 0.8886 | 0.8587 | 0.0299 |

## Claude-Claimed Fold Differentials

| metric | selected_mean | other_mean | delta |
| --- | --- | --- | --- |
| btc_return_pct | -5.4421 | 6.3273 | -11.7693 |
| btc_vol_24h_mean | 0.4187 | 0.4141 | 0.0046 |
| btc_vol_72h_mean | 0.4406 | 0.4302 | 0.0104 |
| btc_vol_168h_mean | 0.4514 | 0.4371 | 0.0143 |
| btc_side_long_share | 0.1754 | 0.233 | -0.0576 |
| btc_side_short_share | 0.2167 | 0.1689 | 0.0478 |
| btc_h4_long_share | 0.4242 | 0.5525 | -0.1283 |
| btc_h4_short_share | 0.5758 | 0.4475 | 0.1283 |
| btc_h4_adx_mean | 27.2204 | 27.6438 | -0.4234 |
| btc_sq120_mean | 0.2264 | 0.2223 | 0.0041 |
| btc_sq240_mean | 0.2281 | 0.2361 | -0.0079 |
| btc_volume_z_mean | 0.025 | 0.0315 | -0.0066 |
| btc_abs_shock_gt2_share | 0.0623 | 0.0621 | 0.0002 |
| btc_abs_shock_gt3_share | 0.0225 | 0.0211 | 0.0014 |
| btc_funding_mean | 0.0 | 0.0001 | -0.0 |
| btc_funding_abs_mean | 0.0001 | 0.0001 | -0.0 |
| btc_funding_positive_share | 0.8167 | 0.9058 | -0.0892 |

## Decision

Yes, the bot can eventually choose timeframe/regime dynamically, but only
through an explicit regime-permission layer that is tested out-of-sample.
This diagnostic is the evidence-gathering step for that layer.
