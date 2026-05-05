import math
import unittest

import numpy as np
import pandas as pd

import hurst_gate
import hurst_mtf_momentum_report
import mtf_momentum_signal
import vol_target_sizing


def _ohlcv(index, close_values, *, volume=100.0):
    close = pd.Series(close_values, index=index, dtype=float)
    open_ = close.shift(1).fillna(close.iloc[0] * 0.999)
    high = pd.concat([open_, close], axis=1).max(axis=1) * 1.002
    low = pd.concat([open_, close], axis=1).min(axis=1) * 0.998
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": float(volume),
        },
        index=index,
    )


class HurstMtfMomentumTests(unittest.TestCase):
    def test_hurst_dfa_separates_persistent_and_anti_persistent_series(self):
        rng = np.random.default_rng(7)
        block_signs = rng.choice([-1.0, 1.0], size=80)
        persistent = np.repeat(block_signs, 10) + rng.normal(0.0, 0.05, size=800)
        anti = np.tile([1.0, -1.0], 400) + rng.normal(0.0, 0.05, size=800)

        persistent_h = hurst_gate.hurst_dfa(persistent)
        anti_h = hurst_gate.hurst_dfa(anti)
        self.assertTrue(math.isfinite(persistent_h))
        self.assertTrue(math.isfinite(anti_h))
        self.assertGreater(persistent_h, anti_h + 0.20)
        self.assertEqual(hurst_gate.regime_from_hurst(0.56), "trend")
        self.assertEqual(hurst_gate.regime_from_hurst(0.44), "anti_persistent")

    def test_rolling_hurst_rs_returns_finite_sanity_values(self):
        idx = pd.date_range("2026-01-01", periods=260, freq="4h", tz="UTC")
        returns = pd.Series(np.sin(np.arange(260) / 8.0) * 0.01, index=idx)
        values = hurst_gate.rolling_hurst_rs(returns, window=80).dropna()
        self.assertFalse(values.empty)
        self.assertTrue(values.apply(math.isfinite).all())
        audit = hurst_gate.hurst_bias_audit_row()
        self.assertTrue(audit["lookahead_safe"])

    def _signal_frames(self):
        idx_4h = pd.date_range("2026-03-01", periods=90, freq="4h", tz="UTC")
        idx_1h = pd.date_range(idx_4h[0] - pd.Timedelta(hours=120), periods=90 * 4 + 120, freq="1h", tz="UTC")
        idx_1d = pd.date_range("2025-06-01", periods=280, freq="1D", tz="UTC")
        df_4h = _ohlcv(idx_4h, np.linspace(100.0, 145.0, len(idx_4h)), volume=150.0)
        df_1d = _ohlcv(idx_1d, np.linspace(80.0, 150.0, len(idx_1d)), volume=1000.0)
        df_1h = _ohlcv(idx_1h, np.linspace(90.0, 145.0, len(idx_1h)), volume=100.0)
        trigger_idx = df_1h.index.get_loc(idx_4h[-1] - pd.Timedelta(hours=1))
        prior_high = float(df_1h["high"].iloc[trigger_idx - 20 : trigger_idx].max())
        df_1h.iloc[trigger_idx, df_1h.columns.get_loc("close")] = prior_high * 1.02
        df_1h.iloc[trigger_idx, df_1h.columns.get_loc("high")] = prior_high * 1.025
        df_1h.iloc[trigger_idx, df_1h.columns.get_loc("volume")] = 1000.0
        hurst = pd.Series(0.64, index=df_4h.index)
        return df_1d, df_4h, df_1h, hurst

    def _short_signal_frames(self):
        idx_4h = pd.date_range("2026-03-01", periods=90, freq="4h", tz="UTC")
        idx_1h = pd.date_range(idx_4h[0] - pd.Timedelta(hours=120), periods=90 * 4 + 120, freq="1h", tz="UTC")
        idx_1d = pd.date_range("2025-06-01", periods=280, freq="1D", tz="UTC")
        df_4h = _ohlcv(idx_4h, np.linspace(145.0, 100.0, len(idx_4h)), volume=150.0)
        df_1d = _ohlcv(idx_1d, np.linspace(150.0, 80.0, len(idx_1d)), volume=1000.0)
        df_1h = _ohlcv(idx_1h, np.linspace(145.0, 90.0, len(idx_1h)), volume=100.0)
        trigger_idx = df_1h.index.get_loc(idx_4h[-1] - pd.Timedelta(hours=1))
        prior_low = float(df_1h["low"].iloc[trigger_idx - 20 : trigger_idx].min())
        df_1h.iloc[trigger_idx, df_1h.columns.get_loc("close")] = prior_low * 0.98
        df_1h.iloc[trigger_idx, df_1h.columns.get_loc("low")] = prior_low * 0.975
        df_1h.iloc[trigger_idx, df_1h.columns.get_loc("volume")] = 1000.0
        hurst = pd.Series(0.64, index=df_4h.index)
        return df_1d, df_4h, df_1h, hurst

    def _strict_pass_inputs(self):
        start_balance = 5000.0
        index = pd.date_range("2023-01-01", "2026-01-01", periods=120, tz="UTC")
        equity_values = [start_balance]
        for idx in range(1, len(index)):
            if idx % 17 == 0:
                multiplier = 0.996
            elif idx % 9 == 0:
                multiplier = 0.998
            else:
                multiplier = 1.015
            equity_values.append(equity_values[-1] * multiplier)
        severe_equity = pd.DataFrame({"equity": equity_values}, index=index)

        top_count = 10
        pips = [6.0] * top_count + [40.0 / 190.0] * 190
        date_cycle = [
            "2024-08-05T12:00:00Z",
            "2025-10-10T12:00:00Z",
            "2024-01-15T12:00:00Z",
            "2024-02-15T12:00:00Z",
            "2024-03-15T12:00:00Z",
            "2024-04-15T12:00:00Z",
            "2024-05-15T12:00:00Z",
            "2024-06-15T12:00:00Z",
            "2024-07-15T12:00:00Z",
            "2024-09-15T12:00:00Z",
            "2024-10-15T12:00:00Z",
            "2024-11-15T12:00:00Z",
        ]
        symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "BNB/USDT:USDT"]
        severe_trades = pd.DataFrame(
            {
                "symbol": [symbols[idx % len(symbols)] for idx in range(200)],
                "exit_time": [date_cycle[idx % len(date_cycle)] for idx in range(200)],
                "pnl": pips,
            }
        )
        fold_rows = pd.DataFrame({"period": range(1, 13), "total_return_pct": [4.0] * 12})
        matrix_rows = []
        for period in range(1, 13):
            matrix_rows.extend(
                [
                    {
                        "period": period,
                        "candidate": "pass_candidate",
                        "train_score": 10.0,
                        "test_return_pct": -1.0 if period == 12 else 4.0,
                        "selected": True,
                    },
                    {
                        "period": period,
                        "candidate": "backup_candidate",
                        "train_score": 8.0,
                        "test_return_pct": 3.0,
                        "selected": False,
                    },
                    {
                        "period": period,
                        "candidate": "weak_candidate",
                        "train_score": 6.0,
                        "test_return_pct": 1.0,
                        "selected": False,
                    },
                ]
            )
        matrix = pd.DataFrame(matrix_rows)
        return severe_trades, severe_equity, fold_rows, matrix, start_balance

    def test_mtf_momentum_signal_uses_closed_parent_bars(self):
        df_1d, df_4h, df_1h, hurst = self._signal_frames()
        frame = mtf_momentum_signal.build_signal_frame(
            df_1d=df_1d,
            df_4h=df_4h,
            df_1h=df_1h,
            hurst_series=hurst,
            volume_z_min=1.0,
        )
        signal = mtf_momentum_signal.row_to_signal(frame.iloc[-1], symbol="BTC/USDT:USDT", volume_z_min=1.0)
        self.assertTrue(signal.is_entry)
        self.assertEqual(signal.side, "long")
        self.assertIn("h1:donchian_breakout_recent", signal.gate_reasons)

    def test_mtf_momentum_signal_supports_short_side(self):
        df_1d, df_4h, df_1h, hurst = self._short_signal_frames()
        frame = mtf_momentum_signal.build_signal_frame(
            df_1d=df_1d,
            df_4h=df_4h,
            df_1h=df_1h,
            hurst_series=hurst,
            volume_z_min=1.0,
        )
        signal = mtf_momentum_signal.row_to_signal(frame.iloc[-1], symbol="BTC/USDT:USDT", volume_z_min=1.0)
        self.assertTrue(signal.is_entry)
        self.assertEqual(signal.side, "short")
        self.assertEqual(int(frame.iloc[-1]["signal_side"]), -1)
        self.assertIn("daily:ema200_aligned", signal.gate_reasons)
        self.assertIn("h1:donchian_breakout_recent", signal.gate_reasons)

    def test_mtf_momentum_signal_uses_direction_specific_volume(self):
        row = pd.Series(
            {
                "daily_side": 1,
                "h4_ema_side": 1,
                "h4_adx": 25.0,
                "h4_hurst": 0.60,
                "h1_long_trigger_age_hours": 1.0,
                "h1_short_trigger_age_hours": 1.0,
                "h1_last_long_trigger_volume_z": 0.5,
                "h1_last_short_trigger_volume_z": 4.0,
            }
        )
        self.assertEqual(mtf_momentum_signal.signal_side_from_row(row, volume_z_min=1.5), 0)
        row["h1_last_long_trigger_volume_z"] = 2.0
        self.assertEqual(mtf_momentum_signal.signal_side_from_row(row, volume_z_min=1.5), 1)

    def test_mtf_momentum_signal_no_future_leak(self):
        df_1d, df_4h, df_1h, hurst = self._signal_frames()
        first = mtf_momentum_signal.build_signal_frame(df_1d=df_1d, df_4h=df_4h, df_1h=df_1h, hurst_series=hurst)
        changed_1h = df_1h.copy()
        changed_4h = df_4h.copy()
        changed_1d = df_1d.copy()
        changed_1h.iloc[-12:, changed_1h.columns.get_loc("close")] *= 10.0
        changed_4h.iloc[-3:, changed_4h.columns.get_loc("close")] *= 10.0
        changed_1d.iloc[-2:, changed_1d.columns.get_loc("close")] *= 10.0
        second = mtf_momentum_signal.build_signal_frame(df_1d=changed_1d, df_4h=changed_4h, df_1h=changed_1h, hurst_series=hurst)
        row = first.index[-8]
        for column in ("daily_side", "h4_ema_side", "h4_hurst", "h1_long_trigger_age_hours", "signal_side"):
            left = first.loc[row, column]
            right = second.loc[row, column]
            if pd.isna(left) and pd.isna(right):
                continue
            self.assertEqual(left, right, column)

    def test_vol_target_sizing_caps_position_margin(self):
        decision = vol_target_sizing.sizing_decision(
            equity=5000.0,
            realized_vol=0.10,
            target_vol=0.60,
            leverage_cap=10.0,
            per_position_max_pct=0.20,
        )
        self.assertEqual(decision.capped_by, "per_position_cap")
        self.assertAlmostEqual(decision.notional, 10000.0)
        self.assertAlmostEqual(decision.margin_required, 1000.0)
        self.assertAlmostEqual(
            vol_target_sizing.portfolio_notional_cap(equity=5000.0, leverage_cap=10.0, per_position_max_pct=0.20, max_concurrent=4),
            40000.0,
        )

    def test_fold_ranges_apply_purge_and_embargo_gap(self):
        index = pd.date_range("2026-01-01", periods=40, freq="4h", tz="UTC")
        folds = hurst_mtf_momentum_report._fold_ranges(
            index,
            train_bars=10,
            test_bars=5,
            folds=2,
            purge_bars=3,
            embargo_bars=2,
        )
        self.assertEqual(len(folds), 2)
        self.assertEqual(folds[0]["train_stop"], 10)
        self.assertEqual(folds[0]["test_start"], 15)
        self.assertEqual(folds[0]["test_index"][0], index[15])
        self.assertEqual(folds[0]["purge_bars"], 3)
        self.assertEqual(folds[0]["embargo_bars"], 2)

    def test_position_notional_expands_at_low_vol_and_shrinks_at_high_vol(self):
        low_vol = vol_target_sizing.sizing_decision(
            equity=1000.0,
            realized_vol=0.01,
            target_vol=0.20,
            leverage_cap=3.0,
            per_position_max_pct=0.50,
        )
        high_vol = vol_target_sizing.sizing_decision(
            equity=1000.0,
            realized_vol=2.0,
            target_vol=0.20,
            leverage_cap=3.0,
            per_position_max_pct=0.50,
        )
        self.assertEqual(low_vol.capped_by, "per_position_cap")
        self.assertAlmostEqual(low_vol.realized_vol, 0.05)
        self.assertAlmostEqual(low_vol.notional, 1500.0)
        self.assertEqual(high_vol.capped_by, "vol_target")
        self.assertAlmostEqual(high_vol.notional, 100.0)
        self.assertGreater(low_vol.notional, high_vol.notional)

    def test_report_helpers_measure_stitch_tail_contribution_and_crisis(self):
        idx_a = pd.date_range("2026-01-01", periods=2, freq="4h", tz="UTC")
        idx_b = pd.date_range("2026-01-02", periods=2, freq="4h", tz="UTC")
        stitched = hurst_mtf_momentum_report.stitch_equity(
            [
                pd.DataFrame({"equity": [100.0, 110.0]}, index=idx_a),
                pd.DataFrame({"equity": [200.0, 220.0]}, index=idx_b),
            ],
            start_balance=1000.0,
        )
        self.assertEqual(stitched["equity"].round(6).tolist(), [1000.0, 1100.0, 1100.0, 1210.0])

        trades = pd.DataFrame(
            {
                "symbol": ["A"] * 5 + ["B"] * 5 + ["C"] * 10,
                "exit_time": ["2024-08-05T12:00:00Z", "2025-10-10T12:00:00Z"] + ["2024-01-01T00:00:00Z"] * 18,
                "pnl": [60.0] + [40.0 / 19.0] * 19,
            }
        )
        self.assertAlmostEqual(hurst_mtf_momentum_report.tail_capture(trades), 0.60)
        self.assertAlmostEqual(hurst_mtf_momentum_report.contribution_share(trades, "symbol"), 68.42105263157895 / 100.0)
        crisis = hurst_mtf_momentum_report.crisis_alpha(trades)
        self.assertEqual(crisis["2024-08-05"], {"pnl": 60.0, "trades": 1, "ok": True})
        self.assertEqual(crisis["2025-10-10"], {"pnl": round(40.0 / 19.0, 4), "trades": 1, "ok": True})

    def test_strict_gate_summary_returns_benchmark_only_for_failed_synthetic_sample(self):
        severe_equity = pd.DataFrame(
            {"equity": [5000.0, 4990.0, 4980.0]},
            index=pd.date_range("2026-01-01", periods=3, freq="4h", tz="UTC"),
        )
        summary = hurst_mtf_momentum_report.strict_gate_summary(
            severe_trades=pd.DataFrame(columns=["symbol", "exit_time", "pnl"]),
            severe_equity=severe_equity,
            fold_rows=pd.DataFrame({"total_return_pct": [-1.0, 2.0]}),
            matrix=pd.DataFrame(),
            candidate_count=2,
            start_balance=5000.0,
        )
        self.assertFalse(summary["ok"])
        self.assertEqual(summary["status"], "benchmark_only")
        self.assertFalse(summary["checks"]["sample_at_least_200_trades"])
        self.assertFalse(summary["checks"]["pbo_below_0_30"])
        self.assertIn("sample_at_least_200_trades", summary["failed_checks"])

    def test_strict_gate_summary_accepts_zero_pbo_value(self):
        severe_trades, severe_equity, fold_rows, matrix, start_balance = self._strict_pass_inputs()
        summary = hurst_mtf_momentum_report.strict_gate_summary(
            severe_trades=severe_trades,
            severe_equity=severe_equity,
            fold_rows=fold_rows,
            matrix=matrix,
            candidate_count=1,
            start_balance=start_balance,
        )
        self.assertLessEqual(summary["pbo"]["pbo"], 0.3)
        self.assertTrue(summary["checks"]["pbo_below_0_30"])

    def test_strict_gate_summary_passes_when_all_synthetic_gates_are_met(self):
        severe_trades, severe_equity, fold_rows, matrix, start_balance = self._strict_pass_inputs()
        summary = hurst_mtf_momentum_report.strict_gate_summary(
            severe_trades=severe_trades,
            severe_equity=severe_equity,
            fold_rows=fold_rows,
            matrix=matrix,
            candidate_count=1,
            start_balance=start_balance,
        )
        self.assertTrue(summary["ok"], summary["failed_checks"])
        self.assertEqual(summary["status"], "pass")
        self.assertEqual(summary["failed_checks"], [])
        self.assertEqual(summary["sample_trades"], 200)
        self.assertEqual(summary["positive_folds"], 12)
        self.assertAlmostEqual(summary["tail_capture"], 0.6)
        self.assertTrue(all(summary["checks"].values()))

    def test_candidate_grid_is_fixed_and_not_symbol_selected(self):
        candidates = hurst_mtf_momentum_report.generate_candidates()
        self.assertEqual(len(candidates), 72)
        self.assertEqual(hurst_mtf_momentum_report.UNIVERSE[0], "BTC/USDT:USDT")
        self.assertIn("DOGE/USDT:USDT", hurst_mtf_momentum_report.UNIVERSE)

    def test_loss_cooldown_blocks_same_symbol_reentry_after_losing_exit(self):
        index = pd.date_range("2026-01-01", periods=8, freq="4h", tz="UTC")
        arrays = hurst_mtf_momentum_report.FeatureArrays(
            symbol="BTC/USDT:USDT",
            entry_open=np.full(8, 100.0),
            entry_high=np.full(8, 101.0),
            entry_low=np.full(8, 96.0),
            entry_close=np.full(8, 99.0),
            h4_atr=np.full(8, 1.0),
            h4_hurst=np.full(8, 0.60),
            h4_adx=np.full(8, 30.0),
            h4_ema_side=np.full(8, 1.0),
            daily_side=np.full(8, 1.0),
            h1_last_trigger_volume_z=np.full(8, 2.0),
            h1_last_long_trigger_volume_z=np.full(8, 2.0),
            h1_last_short_trigger_volume_z=np.full(8, 0.0),
            h1_long_trigger_age_hours=np.zeros(8),
            h1_short_trigger_age_hours=np.full(8, 99.0),
            realized_vol_30d=np.full(8, 0.50),
        )
        data = hurst_mtf_momentum_report.BacktestData(
            index=index,
            symbols=("BTC/USDT:USDT",),
            by_symbol={"BTC/USDT:USDT": arrays},
        )
        candidate = hurst_mtf_momentum_report.Candidate(
            hurst_min=0.53,
            hurst_exit=0.43,
            adx_min=20.0,
            volume_z_min=1.2,
            target_vol=0.45,
        )
        signals = {"BTC/USDT:USDT": np.ones(8, dtype="int8")}
        no_cooldown_trades, _, _ = hurst_mtf_momentum_report._run_candidate_backtest_arrays(
            data,
            0,
            8,
            candidate,
            signals,
            start_balance=5000.0,
            loss_cooldown_bars=0,
        )
        cooldown_trades, _, _ = hurst_mtf_momentum_report._run_candidate_backtest_arrays(
            data,
            0,
            8,
            candidate,
            signals,
            start_balance=5000.0,
            loss_cooldown_bars=2,
        )

        self.assertGreater(len(no_cooldown_trades), len(cooldown_trades))
        self.assertFalse(
            (
                pd.to_datetime(cooldown_trades["entry_time"], utc=True)
                == pd.to_datetime(cooldown_trades["exit_time"], utc=True).shift()
            ).any()
        )


if __name__ == "__main__":
    unittest.main()
