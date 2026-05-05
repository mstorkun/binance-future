import unittest

import numpy as np
import pandas as pd

import htf_reversion_report
import htf_reversion_signal


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


class HtfReversionTests(unittest.TestCase):
    def test_signal_side_accepts_support_reclaim(self):
        row = pd.Series(
            {
                "daily_side": 0,
                "h4_rsi": 28.0,
                "h4_adx": 18.0,
                "h4_volume_z": 1.2,
                "lb60_support_gap_atr": -0.35,
                "lb60_support_reclaim_atr": 0.45,
                "lb60_resistance_gap_atr": 5.0,
                "lb60_resistance_reclaim_atr": 4.0,
                "lb60_range_width_atr": 6.0,
            }
        )
        side = htf_reversion_signal.signal_side_from_row(
            row,
            level_lookback=60,
            rsi_low=30.0,
            max_adx=22.0,
            touch_atr_mult=0.25,
            volume_z_min=1.0,
        )
        self.assertEqual(side, 1)

    def test_signal_side_accepts_resistance_rejection(self):
        row = pd.Series(
            {
                "daily_side": 0,
                "h4_rsi": 74.0,
                "h4_adx": 20.0,
                "h4_volume_z": 0.5,
                "lb120_support_gap_atr": 5.0,
                "lb120_support_reclaim_atr": 4.0,
                "lb120_resistance_gap_atr": -0.20,
                "lb120_resistance_reclaim_atr": 0.35,
                "lb120_range_width_atr": 5.0,
            }
        )
        side = htf_reversion_signal.signal_side_from_row(
            row,
            level_lookback=120,
            rsi_high=70.0,
            max_adx=22.0,
            touch_atr_mult=0.25,
        )
        self.assertEqual(side, -1)

    def test_signal_frame_uses_closed_parent_bars_without_future_leak(self):
        idx_4h = pd.date_range("2026-01-01", periods=240, freq="4h", tz="UTC")
        idx_1d = pd.date_range("2025-01-01", periods=420, freq="1D", tz="UTC")
        df_4h = _ohlcv(idx_4h, 100.0 + np.sin(np.arange(len(idx_4h)) / 8.0) * 4.0, volume=100.0)
        df_1d = _ohlcv(idx_1d, np.linspace(80.0, 120.0, len(idx_1d)), volume=1000.0)

        first = htf_reversion_signal.build_signal_frame(df_1d=df_1d, df_4h=df_4h)
        changed_4h = df_4h.copy()
        changed_1d = df_1d.copy()
        changed_4h.iloc[-12:, changed_4h.columns.get_loc("close")] *= 3.0
        changed_4h.iloc[-12:, changed_4h.columns.get_loc("high")] *= 3.0
        changed_1d.iloc[-3:, changed_1d.columns.get_loc("close")] *= 3.0
        second = htf_reversion_signal.build_signal_frame(df_1d=changed_1d, df_4h=changed_4h)

        row = first.index[-30]
        for column in ("lb60_support", "lb60_resistance", "h4_rsi", "h4_adx", "daily_side"):
            left = first.loc[row, column]
            right = second.loc[row, column]
            if pd.isna(left) and pd.isna(right):
                continue
            self.assertEqual(left, right, column)

    def test_candidate_grid_count_and_debug_cap(self):
        self.assertEqual(len(htf_reversion_report.generate_candidates()), 324)
        capped = htf_reversion_report.generate_candidates(max_candidates=5)
        self.assertEqual(len(capped), 5)
        self.assertEqual(capped[0].level_lookback, 60)

    def test_candidate_signals_vectorize_long_and_short(self):
        index = pd.date_range("2026-01-01", periods=3, freq="4h", tz="UTC")
        arrays = htf_reversion_report.FeatureArrays(
            symbol="BTC",
            entry_open=np.array([100.0, 100.0, 100.0]),
            entry_high=np.array([101.0, 101.0, 101.0]),
            entry_low=np.array([99.0, 99.0, 99.0]),
            entry_close=np.array([100.0, 100.0, 100.0]),
            h4_atr=np.array([2.0, 2.0, 2.0]),
            h4_rsi=np.array([28.0, 75.0, 50.0]),
            h4_adx=np.array([18.0, 18.0, 18.0]),
            h4_volume_z=np.array([1.2, 1.2, 1.2]),
            daily_side=np.array([0.0, 0.0, 0.0]),
            realized_vol_30d=np.array([0.50, 0.50, 0.50]),
            support={60: np.array([98.0, 98.0, 98.0]), 120: np.zeros(3), 180: np.zeros(3)},
            resistance={60: np.array([104.0, 104.0, 104.0]), 120: np.zeros(3), 180: np.zeros(3)},
            support_gap_atr={60: np.array([-0.20, 4.0, 4.0]), 120: np.zeros(3), 180: np.zeros(3)},
            support_reclaim_atr={60: np.array([0.40, 4.0, 4.0]), 120: np.zeros(3), 180: np.zeros(3)},
            resistance_gap_atr={60: np.array([4.0, -0.10, 4.0]), 120: np.zeros(3), 180: np.zeros(3)},
            resistance_reclaim_atr={60: np.array([4.0, 0.30, 4.0]), 120: np.zeros(3), 180: np.zeros(3)},
            range_width_atr={60: np.array([4.0, 4.0, 4.0]), 120: np.zeros(3), 180: np.zeros(3)},
        )
        data = htf_reversion_report.BacktestData(index=index, symbols=("BTC",), by_symbol={"BTC": arrays})
        candidate = htf_reversion_report.Candidate(
            level_lookback=60,
            rsi_low=30.0,
            rsi_high=70.0,
            max_adx=22.0,
            touch_atr_mult=0.25,
            max_reclaim_atr=1.5,
            target_vol=0.50,
            volume_z_min=1.0,
            avoid_daily_opposite=True,
        )
        sides = htf_reversion_report.candidate_signal_sides(data, candidate)["BTC"].tolist()
        self.assertEqual(sides, [1, -1, 0])


if __name__ == "__main__":
    unittest.main()

