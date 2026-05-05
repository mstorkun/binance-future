import unittest

import pandas as pd

import hurst_mtf_trade_diagnostics as diagnostics


class HurstMtfTradeDiagnosticsTests(unittest.TestCase):
    def test_profit_factor_and_group_summary(self):
        trades = pd.DataFrame(
            {
                "exit_reason": ["hard_stop", "hard_stop", "trailing_stop"],
                "pnl": [-10.0, -5.0, 30.0],
            }
        )
        self.assertAlmostEqual(diagnostics.profit_factor(trades["pnl"]), 2.0)
        rows = diagnostics.summarize_by(trades, ["exit_reason"])
        by_reason = {row["exit_reason"]: row for row in rows}
        self.assertEqual(by_reason["hard_stop"]["trades"], 2)
        self.assertAlmostEqual(by_reason["hard_stop"]["pnl"], -15.0)
        self.assertEqual(by_reason["trailing_stop"]["win_rate"], 1.0)

    def test_reentry_diagnostics_separates_losing_and_winning_followups(self):
        trades = pd.DataFrame(
            {
                "symbol": ["BTC", "BTC", "BTC", "ETH", "ETH"],
                "entry_time": [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T04:00:00Z",
                    "2026-01-02T08:00:00Z",
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T04:00:00Z",
                ],
                "exit_time": [
                    "2026-01-01T04:00:00Z",
                    "2026-01-01T08:00:00Z",
                    "2026-01-02T12:00:00Z",
                    "2026-01-01T04:00:00Z",
                    "2026-01-01T08:00:00Z",
                ],
                "side": ["long", "long", "short", "short", "short"],
                "exit_reason": ["hard_stop", "trailing_stop", "hard_stop", "trailing_stop", "time_stop"],
                "pnl": [-10.0, 6.0, -2.0, 12.0, -3.0],
            }
        )
        result = diagnostics.reentry_diagnostics(trades)
        hypothesis = result["cooldown_hypothesis"]
        self.assertEqual(hypothesis["losing_exit_reentry_trades"], 1)
        self.assertEqual(hypothesis["losing_exit_reentry_pnl"], 6.0)
        self.assertEqual(hypothesis["winning_trailing_reentry_trades"], 2)
        self.assertEqual(hypothesis["winning_trailing_reentry_pnl"], -5.0)
        self.assertIn("next_variant", hypothesis)

    def test_build_diagnostics_picks_cooldown_variant(self):
        trades = pd.DataFrame(
            {
                "period": [1, 1, 2, 2],
                "symbol": ["BTC", "BTC", "ETH", "ETH"],
                "entry_time": [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T04:00:00Z",
                    "2026-01-02T00:00:00Z",
                    "2026-01-02T04:00:00Z",
                ],
                "exit_time": [
                    "2026-01-01T04:00:00Z",
                    "2026-01-01T08:00:00Z",
                    "2026-01-02T04:00:00Z",
                    "2026-01-02T08:00:00Z",
                ],
                "side": ["long", "long", "short", "short"],
                "exit_reason": ["hard_stop", "time_stop", "trailing_stop", "hard_stop"],
                "pnl": [-10.0, -2000.0, 30.0, -8.0],
                "bars_held": [1, 1, 1, 1],
                "reached_1r": [False, False, True, False],
            }
        )
        results = pd.DataFrame(
            {
                "scenario": ["baseline", "severe"],
                "total_return_pct": [-5.0, -10.0],
            }
        )
        report = diagnostics.build_diagnostics(trades, results)
        self.assertEqual(report["status"], "diagnostic_only")
        self.assertEqual(report["next_candidate"]["name"], "HURST_MTF_COOLDOWN_V2")
        self.assertLess(report["key_numbers"]["baseline_compound_return_pct"], 0.0)

    def test_build_diagnostics_picks_cost_robust_variant_after_cooldown_leak_is_small(self):
        trades = pd.DataFrame(
            {
                "period": [1, 1],
                "symbol": ["BTC", "BTC"],
                "entry_time": ["2026-01-01T00:00:00Z", "2026-01-03T00:00:00Z"],
                "exit_time": ["2026-01-01T04:00:00Z", "2026-01-03T04:00:00Z"],
                "side": ["long", "long"],
                "exit_reason": ["trailing_stop", "hard_stop"],
                "pnl": [30.0, -8.0],
                "bars_held": [1, 1],
                "reached_1r": [True, False],
            }
        )
        results = pd.DataFrame(
            {
                "scenario": ["baseline", "severe"],
                "total_return_pct": [20.0, -30.0],
            }
        )
        report = diagnostics.build_diagnostics(trades, results)
        self.assertEqual(report["next_candidate"]["name"], "HURST_MTF_COST_ROBUST_V3")
        self.assertEqual(report["key_numbers"]["selected_next_candidate"], "HURST_MTF_COST_ROBUST_V3")


if __name__ == "__main__":
    unittest.main()
