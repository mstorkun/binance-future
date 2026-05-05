import unittest

import pandas as pd

import hurst_mtf_false_negative_audit as audit


def _matrix():
    rows = []
    for period in range(1, 13):
        for candidate in range(72):
            rows.append(
                {
                    "period": period,
                    "candidate": f"candidate_{candidate}",
                    "selected": candidate == 0,
                }
            )
    return pd.DataFrame(rows)


class HurstMtfFalseNegativeAuditTests(unittest.TestCase):
    def test_compound_return_pct_compounds_fold_returns(self):
        result = audit.compound_return_pct(pd.Series([10.0, -10.0]))
        self.assertAlmostEqual(result, -1.0)

    def test_build_audit_flags_review_errors_but_confirms_benchmark_only(self):
        severe_returns = [-1.0, 2.0, -3.0, -4.0, -5.0, -6.0, -7.0, -8.0, -9.0, -10.0, -11.0, 7.0]
        scenario_rows = [
            {"period": period, "scenario": "severe", "total_return_pct": value}
            for period, value in enumerate(severe_returns, start=1)
        ] + [
            {"period": period, "scenario": "baseline", "total_return_pct": -1.0}
            for period in range(1, 13)
        ]
        trades = pd.DataFrame(
            {
                "symbol": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"],
                "exit_time": ["2024-08-05T12:00:00Z", "2025-10-10T12:00:00Z", "2025-12-13T12:00:00Z"],
                "pnl": [10.0, -5.0, 1.0],
            }
        )
        strict = {
            "status": "benchmark_only",
            "checks": {
                "net_cagr_after_severe_cost_pct": False,
                "pbo_below_0_30": True,
                "walk_forward_positive_folds_7_of_12": False,
                "dsr_proxy_non_negative": False,
                "sortino_at_least_2": False,
                "no_symbol_over_40_pct_pnl": True,
                "no_month_over_25_pct_pnl": True,
                "tail_capture_50_to_80_pct": False,
                "crisis_alpha_positive": False,
                "sample_at_least_200_trades": True,
            },
            "failed_checks": [
                "net_cagr_after_severe_cost_pct",
                "walk_forward_positive_folds_7_of_12",
                "dsr_proxy_non_negative",
                "sortino_at_least_2",
                "tail_capture_50_to_80_pct",
                "crisis_alpha_positive",
            ],
            "metrics": {"final_equity": 230.204, "total_return_pct": -95.3959},
            "sample_trades": 3,
            "tail_capture": 0.9091,
            "symbol_pnl_share": 0.9091,
            "month_pnl_share": 0.9091,
            "crisis_alpha": {
                "2024-08-05": {"pnl": 10.0, "trades": 1, "ok": True},
                "2025-10-10": {"pnl": -5.0, "trades": 1, "ok": False},
            },
        }

        result = audit.build_audit(
            report_json={"strict": strict, "scenario_rows": scenario_rows},
            matrix=_matrix(),
            trades=trades,
        )

        self.assertEqual(result["status"], "review_errors_but_benchmark_only_confirmed")
        self.assertTrue(all(result["consistency_checks"].values()), result["consistency_checks"])
        self.assertTrue(result["false_negative_checks"]["review_contains_material_errors"])
        self.assertTrue(result["false_negative_checks"]["artifact_recomputations_match"])
        self.assertTrue(result["false_negative_checks"]["baseline_also_negative"])
        self.assertEqual(result["matrix"]["min_candidates_per_fold"], 72)
        claim_verdicts = {row["claim"]: row["verdict"] for row in result["review_claims"]}
        self.assertEqual(claim_verdicts["both_crisis_days_lost"], "incorrect")
        self.assertEqual(claim_verdicts["start_1000_to_230"], "incorrect")
        self.assertEqual(claim_verdicts["folds_6_to_12_all_negative"], "incorrect")


if __name__ == "__main__":
    unittest.main()
