import unittest

import numpy as np
import pandas as pd

import range_reversion_report
import range_reversion_signal


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


class RangeReversionTests(unittest.TestCase):
    def test_signal_side_accepts_long_extreme(self):
        row = pd.Series(
            {
                "daily_side": 0,
                "h4_adx": 18.0,
                "h1_rsi": 32.0,
                "lb48_close_z": -1.7,
                "lb48_low_z": -1.9,
                "lb48_high_z": -1.2,
                "lb48_band_width_pct": 0.02,
            }
        )
        side = range_reversion_signal.signal_side_from_row(row, lookback=48, z_min=1.5, rsi_low=35.0)
        self.assertEqual(side, 1)

    def test_signal_side_accepts_reclaim_short(self):
        row = pd.Series(
            {
                "daily_side": 0,
                "h4_adx": 20.0,
                "h1_rsi": 68.0,
                "lb24_close_z": 1.2,
                "lb24_low_z": 0.8,
                "lb24_high_z": 1.8,
                "lb24_band_width_pct": 0.02,
            }
        )
        side = range_reversion_signal.signal_side_from_row(
            row,
            lookback=24,
            z_min=1.5,
            rsi_high=65.0,
            require_reclaim=True,
        )
        self.assertEqual(side, -1)

    def test_signal_frame_uses_closed_bars_without_future_leak(self):
        idx_1h = pd.date_range("2026-01-01", periods=360, freq="1h", tz="UTC")
        idx_1d = pd.date_range("2025-01-01", periods=430, freq="1D", tz="UTC")
        df_1h = _ohlcv(idx_1h, 100.0 + np.sin(np.arange(len(idx_1h)) / 7.0) * 3.0)
        df_4h = range_reversion_report.resample_ohlcv(df_1h, "4h")
        df_1d = _ohlcv(idx_1d, np.linspace(80.0, 125.0, len(idx_1d)), volume=1000.0)

        first = range_reversion_signal.build_signal_frame(df_1h=df_1h, df_4h=df_4h, df_1d=df_1d)
        changed_1h = df_1h.copy()
        changed_1d = df_1d.copy()
        changed_1h.iloc[-24:, changed_1h.columns.get_loc("close")] *= 3.0
        changed_1h.iloc[-24:, changed_1h.columns.get_loc("high")] *= 3.0
        changed_1d.iloc[-3:, changed_1d.columns.get_loc("close")] *= 3.0
        second = range_reversion_signal.build_signal_frame(
            df_1h=changed_1h,
            df_4h=range_reversion_report.resample_ohlcv(changed_1h, "4h"),
            df_1d=changed_1d,
        )

        row = first.index[-60]
        for column in ("lb24_mean", "lb24_close_z", "h1_rsi", "h4_adx", "daily_side"):
            left = first.loc[row, column]
            right = second.loc[row, column]
            if pd.isna(left) and pd.isna(right):
                continue
            self.assertEqual(left, right, column)

    def test_candidate_grid_count_and_debug_cap(self):
        self.assertEqual(len(range_reversion_report.generate_candidates()), 96)
        capped = range_reversion_report.generate_candidates(max_candidates=7)
        self.assertEqual(len(capped), 7)
        self.assertEqual(capped[0].lookback, 24)

    def test_candidate_signals_vectorize_long_and_short(self):
        index = pd.date_range("2026-01-01", periods=3, freq="1h", tz="UTC")
        arrays = range_reversion_report.FeatureArrays(
            symbol="BTC",
            entry_open=np.array([100.0, 100.0, 100.0]),
            entry_high=np.array([101.0, 101.0, 101.0]),
            entry_low=np.array([99.0, 99.0, 99.0]),
            entry_close=np.array([100.0, 100.0, 100.0]),
            h1_atr=np.array([2.0, 2.0, 2.0]),
            h1_rsi=np.array([32.0, 68.0, 50.0]),
            h4_adx=np.array([18.0, 18.0, 18.0]),
            daily_side=np.array([0.0, 0.0, 0.0]),
            realized_vol_30d=np.array([0.50, 0.50, 0.50]),
            mean={24: np.array([102.0, 98.0, 100.0]), 48: np.zeros(3), 72: np.zeros(3)},
            close_z={24: np.array([-1.7, 1.8, 0.0]), 48: np.zeros(3), 72: np.zeros(3)},
            low_z={24: np.array([-2.0, 1.2, 0.0]), 48: np.zeros(3), 72: np.zeros(3)},
            high_z={24: np.array([-1.2, 2.0, 0.0]), 48: np.zeros(3), 72: np.zeros(3)},
            band_width_pct={24: np.array([0.02, 0.02, 0.02]), 48: np.zeros(3), 72: np.zeros(3)},
        )
        data = range_reversion_report.BacktestData(index=index, symbols=("BTC",), by_symbol={"BTC": arrays})
        candidate = range_reversion_report.Candidate(
            lookback=24,
            z_min=1.5,
            rsi_low=35.0,
            rsi_high=65.0,
            h4_adx_max=22.0,
            target_vol=0.50,
            stop_atr_mult=1.5,
            take_profit_atr_mult=1.0,
            require_reclaim=False,
        )
        sides = range_reversion_report.candidate_signal_sides(data, candidate)["BTC"].tolist()
        self.assertEqual(sides, [1, -1, 0])


if __name__ == "__main__":
    unittest.main()
