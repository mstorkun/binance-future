# Volatility Breakout Regime Diagnostics - 2026-05-05

Status: diagnostic-only. This does not enable paper, testnet, or live execution.

## Fold Sets

- Current baseline-positive folds: `[6, 7, 8, 11, 12]`
- Current severe-positive folds: `[6]`
- Claude-claimed folds checked separately: `[2, 5, 10, 12]`

## Fold Regime Rows

| period | baseline_return_pct | severe_return_pct | baseline_positive | severe_positive | claude_fold | btc_return_pct | btc_vol_72h_mean | btc_h4_adx_mean | btc_h4_long_share | btc_h4_short_share | btc_funding_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | -1.6889 | -12.0633 | False | False | False | -5.3859 | 0.4404 | 27.9794 | 0.34 | 0.66 | 0.0001 |
| 2 | -9.9196 | -16.1746 | False | False | True | -9.2671 | 0.571 | 28.3322 | 0.33 | 0.67 | 0.0 |
| 3 | -10.8462 | -16.0764 | False | False | False | 27.1315 | 0.3981 | 33.5072 | 0.74 | 0.26 | 0.0001 |
| 4 | -16.8949 | -24.8711 | False | False | False | 23.9533 | 0.5476 | 28.8007 | 0.8333 | 0.1667 | 0.0001 |
| 5 | -1.242 | -4.4633 | False | False | True | 3.1188 | 0.4981 | 22.2105 | 0.4133 | 0.5867 | 0.0001 |
| 6 | 8.3813 | 4.3651 | True | True | False | -18.3856 | 0.5255 | 24.413 | 0.2233 | 0.7767 | 0.0 |
| 7 | 4.3674 | -1.5265 | True | False | False | 38.3424 | 0.4275 | 29.829 | 0.89 | 0.11 | 0.0 |
| 8 | 1.7667 | -4.9494 | True | False | False | 6.2815 | 0.3088 | 24.4993 | 0.58 | 0.42 | 0.0 |
| 9 | -3.4185 | -10.1821 | False | False | False | -3.6682 | 0.317 | 24.267 | 0.4867 | 0.5133 | 0.0001 |
| 10 | -13.6778 | -26.2856 | False | False | True | -1.8089 | 0.3302 | 34.175 | 0.5233 | 0.4767 | 0.0 |
| 11 | 0.5985 | -3.785 | True | False | False | -17.6511 | 0.4763 | 27.8551 | 0.3267 | 0.6733 | 0.0 |
| 12 | 3.6397 | -3.2765 | True | False | True | -13.8111 | 0.3631 | 24.1641 | 0.43 | 0.57 | 0.0001 |

## Group Means

| group | folds | btc_return_pct | btc_vol_72h_mean | btc_h4_adx_mean | btc_h4_long_share | btc_h4_short_share | btc_funding_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_positive | 5 | -1.0448 | 0.4202 | 26.1521 | 0.49 | 0.51 | 0.0 |
| severe_positive | 1 | -18.3856 | 0.5255 | 24.413 | 0.2233 | 0.7767 | 0.0 |
| claude_claimed | 4 | -5.4421 | 0.4406 | 27.2204 | 0.4242 | 0.5758 | 0.0 |

## Severe-Positive Differentials

| metric | selected_mean | other_mean | delta |
| --- | --- | --- | --- |
| btc_return_pct | -18.3856 | 4.2941 | -22.6797 |
| btc_vol_24h_mean | 0.5011 | 0.4079 | 0.0933 |
| btc_vol_72h_mean | 0.5255 | 0.4253 | 0.1002 |
| btc_vol_168h_mean | 0.529 | 0.434 | 0.0951 |
| btc_side_long_share | 0.1042 | 0.2238 | -0.1196 |
| btc_side_short_share | 0.2617 | 0.1778 | 0.0839 |
| btc_h4_long_share | 0.2233 | 0.5358 | -0.3124 |
| btc_h4_short_share | 0.7767 | 0.4642 | 0.3124 |
| btc_h4_adx_mean | 24.413 | 27.7836 | -3.3706 |
| btc_sq120_mean | 0.2257 | 0.2235 | 0.0022 |
| btc_sq240_mean | 0.2485 | 0.232 | 0.0164 |
| btc_volume_z_mean | 0.0468 | 0.0277 | 0.019 |
| btc_abs_shock_gt2_share | 0.0625 | 0.0621 | 0.0004 |
| btc_abs_shock_gt3_share | 0.0208 | 0.0217 | -0.0008 |
| btc_funding_mean | 0.0 | 0.0001 | -0.0 |
| btc_funding_abs_mean | 0.0 | 0.0001 | -0.0 |
| btc_funding_positive_share | 0.8 | 0.883 | -0.083 |

## Baseline-Positive Differentials

| metric | selected_mean | other_mean | delta |
| --- | --- | --- | --- |
| btc_return_pct | -1.0448 | 4.8677 | -5.9124 |
| btc_vol_24h_mean | 0.402 | 0.4254 | -0.0234 |
| btc_vol_72h_mean | 0.4202 | 0.4432 | -0.023 |
| btc_vol_168h_mean | 0.4295 | 0.4508 | -0.0213 |
| btc_side_long_share | 0.2038 | 0.221 | -0.0171 |
| btc_side_short_share | 0.1913 | 0.1801 | 0.0112 |
| btc_h4_long_share | 0.49 | 0.5238 | -0.0338 |
| btc_h4_short_share | 0.51 | 0.4762 | 0.0338 |
| btc_h4_adx_mean | 26.1521 | 28.4674 | -2.3153 |
| btc_sq120_mean | 0.2189 | 0.2271 | -0.0082 |
| btc_sq240_mean | 0.2306 | 0.2354 | -0.0049 |
| btc_volume_z_mean | 0.032 | 0.0274 | 0.0045 |
| btc_abs_shock_gt2_share | 0.0602 | 0.0636 | -0.0034 |
| btc_abs_shock_gt3_share | 0.0217 | 0.0215 | 0.0001 |
| btc_funding_mean | 0.0 | 0.0001 | -0.0 |
| btc_funding_abs_mean | 0.0 | 0.0001 | -0.0 |
| btc_funding_positive_share | 0.86 | 0.8876 | -0.0276 |

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
