# Hurst MTF False-Negative Audit - 2026-05-05

Status: research-only audit. This does not enable paper, testnet, or live execution.

Audit status: `review_errors_but_benchmark_only_confirmed`
Original strict status: `benchmark_only`

## Decision

Do not accept the external review wording as fully correct; it contains material factual errors. Do not promote Phase B either: local artifacts are internally consistent and still show benchmark_only.

## Review Claim Corrections

| claim | verdict | evidence |
| --- | --- | --- |
| both_crisis_days_lost | incorrect | won=2024-08-05 lost=2025-10-10 |
| start_1000_to_230 | incorrect | implied_start=4999.98 final=230.2 total_return_pct=-95.3959 |
| folds_6_to_12_all_negative | incorrect | positive_late_folds=12 |

## Artifact Consistency

| check | pass |
| --- | --- |
| strict_status_present | True |
| gate_count_is_10 | True |
| failed_gate_count_is_6 | True |
| trade_sample_matches_json | True |
| tail_capture_matches_json | True |
| symbol_share_matches_json | True |
| month_share_matches_json | True |
| matrix_full_72_candidates | True |
| matrix_one_selection_per_fold | True |

## False-Negative Checks

| check | pass |
| --- | --- |
| review_contains_material_errors | True |
| artifact_recomputations_match | True |
| baseline_also_negative | True |
| severe_fold_fail_confirmed | True |
| no_debug_candidate_cap | True |
| pbo_gate_passed | True |

## Scenario Compounds

| scenario | folds | positive_folds | compound_return_pct | worst_fold_pct | best_fold_pct |
| --- | --- | --- | --- | --- | --- |
| baseline | 12 | 3 | -73.7979 | -56.0666 | 85.0879 |
| slippage_30bps | 12 | 3 | -84.6084 | -61.0466 | 73.8975 |
| slippage_60bps | 12 | 2 | -94.7197 | -69.4295 | 53.397 |
| funding_2x | 12 | 3 | -77.1096 | -57.5506 | 82.5021 |
| severe | 12 | 2 | -95.3959 | -70.4818 | 51.2228 |

## Crisis Alpha

| date | pnl | trades | ok |
| --- | --- | --- | --- |
| 2024-08-05 | 8140.884 | 9 | True |
| 2025-10-10 | -372.7327 | 2 | False |

## Matrix

| rows | folds | min_candidates_per_fold | max_candidates_per_fold | selected_rows | debug_cap_detected | one_selection_per_fold |
| --- | --- | --- | --- | --- | --- | --- |
| 864 | 12 | 72 | 72 | 12 | False | True |

## Recomputed From Trades

| sample_trades | tail_capture | symbol_pnl_share | month_pnl_share |
| --- | --- | --- | --- |
| 454 | 0.4323 | 0.0049 | 0.0858 |

## Next Research Constraint

Continue the alpha search, but keep Hurst-MTF Phase A as benchmark_only unless a new variant rerun passes every strict gate.
