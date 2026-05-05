import unittest

import numpy as np
import pandas as pd

import volatility_breakout_report
import volatility_breakout_regime_diagnostics
import volatility_breakout_signal


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


class VolatilityBreakoutTests(unittest.TestCase):
    def test_signal_frame_uses_closed_bars_without_future_leak(self):
        idx_1h = pd.date_range("2026-01-01", periods=420, freq="1h", tz="UTC")
        idx_1d = pd.date_range("2025-01-01", periods=420, freq="1D", tz="UTC")
        close = 100.0 + np.sin(np.arange(len(idx_1h)) / 20.0) * 2.0
        df_1h = _ohlcv(idx_1h, close)
        df_4h = volatility_breakout_report.resample_ohlcv(df_1h, "4h")
        df_1d = _ohlcv(idx_1d, np.linspace(80.0, 140.0, len(idx_1d)), volume=1000.0)

        first = volatility_breakout_signal.build_signal_frame(df_1h=df_1h, df_4h=df_4h, df_1d=df_1d, btc_1h=df_1h)
        changed_1h = df_1h.copy()
        changed_4h = df_4h.copy()
        changed_1d = df_1d.copy()
        changed_1h.iloc[-20:, changed_1h.columns.get_loc("close")] *= 3.0
        changed_1h.iloc[-20:, changed_1h.columns.get_loc("high")] *= 3.0
        changed_4h.iloc[-5:, changed_4h.columns.get_loc("close")] *= 3.0
        changed_1d.iloc[-3:, changed_1d.columns.get_loc("close")] *= 3.0
        second = volatility_breakout_signal.build_signal_frame(df_1h=changed_1h, df_4h=changed_4h, df_1d=changed_1d, btc_1h=changed_1h)

        row = first.index[-60]
        for column in ("bo24_high", "bo24_low", "sq120_recent_squeeze", "h4_side", "btc_side", "daily_side"):
            left = first.loc[row, column]
            right = second.loc[row, column]
            if pd.isna(left) and pd.isna(right):
                continue
            self.assertEqual(left, right, column)

    def test_candidate_grid_count_and_debug_cap(self):
        self.assertEqual(len(volatility_breakout_report.generate_candidates()), 216)
        capped = volatility_breakout_report.generate_candidates(max_candidates=7)
        self.assertEqual(len(capped), 7)
        self.assertEqual(capped[0].breakout_lookback, 24)

    def test_candidate_signals_vectorize_long_short_and_wait(self):
        index = pd.date_range("2026-01-01", periods=3, freq="1h", tz="UTC")
        zeros = np.zeros(3)
        arrays = volatility_breakout_report.FeatureArrays(
            symbol="BTC/USDT:USDT",
            entry_open=np.array([100.0, 100.0, 100.0]),
            entry_high=np.array([101.0, 101.0, 101.0]),
            entry_low=np.array([99.0, 99.0, 99.0]),
            entry_close=np.array([100.0, 100.0, 100.0]),
            h1_atr=np.array([1.0, 1.0, 1.0]),
            h1_volume_z=np.array([1.5, 1.5, 1.5]),
            h4_side=np.array([1.0, -1.0, 1.0]),
            h4_adx=np.array([22.0, 22.0, 22.0]),
            daily_side=np.array([1.0, -1.0, 1.0]),
            btc_side=np.array([1.0, -1.0, -1.0]),
            btc_shock_z=np.array([1.0, -1.0, 1.0]),
            realized_vol_30d=np.array([0.50, 0.50, 0.50]),
            breakout_high={24: zeros, 48: zeros, 72: zeros},
            breakout_low={24: zeros, 48: zeros, 72: zeros},
            breakout_range_atr={24: np.array([3.0, 3.0, 3.0]), 48: zeros, 72: zeros},
            breakout_up_atr={24: np.array([0.30, 0.0, 0.30]), 48: zeros, 72: zeros},
            breakout_down_atr={24: np.array([0.0, 0.40, 0.0]), 48: zeros, 72: zeros},
            breakout_up={24: np.array([1.0, 0.0, 1.0]), 48: zeros, 72: zeros},
            breakout_down={24: np.array([0.0, 1.0, 0.0]), 48: zeros, 72: zeros},
            recent_squeeze={120: np.array([0.10, 0.10, 0.10]), 240: zeros},
        )
        data = volatility_breakout_report.BacktestData(
            index=index,
            symbols=("BTC/USDT:USDT",),
            by_symbol={"BTC/USDT:USDT": arrays},
        )
        candidate = volatility_breakout_report.Candidate(
            breakout_lookback=24,
            squeeze_lookback=120,
            squeeze_pctile_max=0.15,
            volume_z_min=1.2,
            h4_adx_min=20.0,
            target_vol=0.45,
        )
        sides = volatility_breakout_report.candidate_signal_sides(data, candidate)["BTC/USDT:USDT"].tolist()
        self.assertEqual(sides, [1, -1, 0])

    def test_metrics_use_1h_timeframe(self):
        index = pd.date_range("2026-01-01", periods=25, freq="1h", tz="UTC")
        equity = pd.DataFrame({"equity": np.linspace(1000.0, 1100.0, len(index))}, index=index)
        metrics = volatility_breakout_report._metrics_1h(pd.DataFrame(), equity, start_balance=1000.0)
        self.assertGreater(metrics["cagr_pct"], 0.0)
        self.assertEqual(metrics["trades"], 0)

    def test_regime_diagnostics_scenario_map_and_diffs(self):
        results = pd.DataFrame(
            {
                "period": [1, 1, 2, 2],
                "scenario": ["baseline", "severe", "baseline", "severe"],
                "total_return_pct": [3.0, -1.0, -2.0, 4.0],
            }
        )
        self.assertEqual(volatility_breakout_regime_diagnostics._scenario_map(results, "baseline"), {1: 3.0, 2: -2.0})
        rows = pd.DataFrame(
            {
                "baseline_positive": [True, False],
                "btc_vol_72h_mean": [0.3, 0.5],
                "btc_h4_adx_mean": [20.0, 30.0],
            }
        )
        diffs = volatility_breakout_regime_diagnostics._diff_table(
            rows,
            "baseline_positive",
            ["btc_vol_72h_mean", "btc_h4_adx_mean"],
        )
        by_metric = {row["metric"]: row for row in diffs}
        self.assertAlmostEqual(by_metric["btc_vol_72h_mean"]["delta"], -0.2)
        self.assertAlmostEqual(by_metric["btc_h4_adx_mean"]["delta"], -10.0)


if __name__ == "__main__":
    unittest.main()
