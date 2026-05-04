from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_LOOKBACK = 40


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    return pd.to_numeric(num / den.replace(0, pd.NA), errors="coerce")


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _true_range(df: pd.DataFrame) -> pd.Series:
    return pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)


def _rolling_slope(series: pd.Series, lookback: int) -> pd.Series:
    def slope(values: np.ndarray) -> float:
        mask = np.isfinite(values)
        if mask.sum() < max(3, lookback // 3):
            return float("nan")
        x = np.arange(len(values), dtype=float)[mask]
        y = values[mask].astype(float)
        if len(np.unique(y)) < 2:
            return 0.0
        return float(np.polyfit(x, y, 1)[0])

    return series.rolling(lookback, min_periods=max(3, lookback // 3)).apply(slope, raw=True)


def add_chart_pattern_features(
    df: pd.DataFrame,
    *,
    prefix: str = "",
    lookback: int = DEFAULT_LOOKBACK,
    min_break_atr: float = 0.10,
    touch_atr: float = 0.35,
) -> pd.DataFrame:
    """Convert chart-screenshot ideas into closed-OHLCV numeric features.

    This module intentionally avoids image parsing. It implements the objective
    version of common visual ideas: range breakout, failed breakout, retest,
    compression, measured move, and crude trend-line convergence.
    """
    out = pd.DataFrame(index=df.index)
    if df.empty:
        return out

    lookback = max(10, int(lookback))
    open_ = pd.to_numeric(df["open"], errors="coerce")
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce")
    tr = _true_range(df)
    atr = tr.ewm(alpha=1.0 / 14.0, adjust=False).mean().replace(0, pd.NA)

    prior_high = high.rolling(lookback, min_periods=max(5, lookback // 3)).max().shift(1)
    prior_low = low.rolling(lookback, min_periods=max(5, lookback // 3)).min().shift(1)
    range_height = (prior_high - prior_low).replace(0, pd.NA)
    older_high = high.rolling(lookback * 2, min_periods=lookback).max().shift(lookback)
    older_low = low.rolling(lookback * 2, min_periods=lookback).min().shift(lookback)
    older_height = (older_high - older_low).replace(0, pd.NA)

    volume_median = volume.rolling(lookback, min_periods=max(5, lookback // 3)).median()
    volume_std = volume.rolling(lookback, min_periods=max(5, lookback // 3)).std(ddof=0)
    touch_band = atr * float(touch_atr)
    near_resistance = (high >= prior_high - touch_band) & (high <= prior_high + touch_band)
    near_support = (low <= prior_low + touch_band) & (low >= prior_low - touch_band)

    break_buffer = atr * float(min_break_atr)
    breakout_up = close > prior_high + break_buffer
    breakout_down = close < prior_low - break_buffer
    wick_break_up = (high > prior_high + break_buffer) & ~breakout_up
    wick_break_down = (low < prior_low - break_buffer) & ~breakout_down

    prev_breakout_up = breakout_up.shift(1).fillna(False)
    prev_breakout_down = breakout_down.shift(1).fillna(False)
    prev_prior_high = prior_high.shift(1)
    prev_prior_low = prior_low.shift(1)
    retest_long = prev_breakout_up & (low <= prev_prior_high + touch_band) & (close > prev_prior_high)
    retest_short = prev_breakout_down & (high >= prev_prior_low - touch_band) & (close < prev_prior_low)

    shifted_high = high.shift(1)
    shifted_low = low.shift(1)
    upper_slope = _rolling_slope(shifted_high, lookback)
    lower_slope = _rolling_slope(shifted_low, lookback)
    slope_spread_atr = _safe_div(upper_slope - lower_slope, atr)
    width_decay = _safe_div(range_height, older_height)
    converging = (slope_spread_atr < 0) & (width_decay < 0.85)
    ascending_triangle = converging & (upper_slope.abs() <= atr * 0.02) & (lower_slope > 0)
    descending_triangle = converging & (lower_slope.abs() <= atr * 0.02) & (upper_slope < 0)
    symmetric_triangle = converging & (upper_slope < 0) & (lower_slope > 0)

    body = (close - open_).abs()
    candle_range = (high - low).replace(0, pd.NA)
    impulse = (_safe_div(body, atr) >= 1.2) & (_safe_div(body, candle_range) >= 0.60)
    impulse_direction = np.sign(close - open_)
    recent_impulse = impulse.rolling(max(3, lookback // 4), min_periods=1).max().shift(1).fillna(False).astype(bool)
    impulse_ret = close.pct_change(max(3, lookback // 4)).shift(1) * 100.0
    flag_compression = recent_impulse & (_safe_div(range_height, atr) <= lookback * 0.55) & (width_decay < 0.90)

    p = prefix
    out[f"{p}pattern_range_high"] = prior_high
    out[f"{p}pattern_range_low"] = prior_low
    out[f"{p}pattern_range_height_atr"] = _safe_div(range_height, atr)
    out[f"{p}pattern_range_compression"] = width_decay
    out[f"{p}pattern_resistance_touches"] = near_resistance.rolling(lookback, min_periods=max(5, lookback // 3)).sum().shift(1)
    out[f"{p}pattern_support_touches"] = near_support.rolling(lookback, min_periods=max(5, lookback // 3)).sum().shift(1)
    out[f"{p}pattern_breakout_up"] = breakout_up.astype(int)
    out[f"{p}pattern_breakout_down"] = breakout_down.astype(int)
    out[f"{p}pattern_wick_break_up"] = wick_break_up.astype(int)
    out[f"{p}pattern_wick_break_down"] = wick_break_down.astype(int)
    out[f"{p}pattern_retest_long"] = retest_long.astype(int)
    out[f"{p}pattern_retest_short"] = retest_short.astype(int)
    out[f"{p}pattern_breakout_distance_atr"] = _safe_div(close - prior_high, atr).where(breakout_up, _safe_div(prior_low - close, atr).where(breakout_down, 0.0))
    out[f"{p}pattern_volume_z"] = (volume - volume_median) / volume_std.replace(0, pd.NA)
    out[f"{p}pattern_upper_slope_atr"] = _safe_div(upper_slope, atr)
    out[f"{p}pattern_lower_slope_atr"] = _safe_div(lower_slope, atr)
    out[f"{p}pattern_slope_spread_atr"] = slope_spread_atr
    out[f"{p}pattern_converging"] = converging.astype(int)
    out[f"{p}pattern_ascending_triangle"] = ascending_triangle.astype(int)
    out[f"{p}pattern_descending_triangle"] = descending_triangle.astype(int)
    out[f"{p}pattern_symmetric_triangle"] = symmetric_triangle.astype(int)
    out[f"{p}pattern_flag_compression"] = flag_compression.astype(int)
    out[f"{p}pattern_impulse_return_pct"] = impulse_ret
    out[f"{p}pattern_measured_move_long_pct"] = _safe_div(range_height, close) * 100.0
    out[f"{p}pattern_measured_move_short_pct"] = _safe_div(range_height, close) * 100.0

    scored = out.apply(lambda row: score_chart_pattern_row(row, prefix=p), axis=1, result_type="expand")
    for column in scored.columns:
        out[column] = scored[column]
    return out.replace([float("inf"), float("-inf")], pd.NA)


def score_chart_pattern_row(row: pd.Series, *, prefix: str = "") -> dict[str, Any]:
    p = prefix
    long_score = 0.0
    short_score = 0.0
    reasons: list[str] = []
    volume_z = _num(row.get(f"{p}pattern_volume_z"))
    resistance_touches = _num(row.get(f"{p}pattern_resistance_touches"))
    support_touches = _num(row.get(f"{p}pattern_support_touches"))
    breakout_distance = _num(row.get(f"{p}pattern_breakout_distance_atr"))

    if _num(row.get(f"{p}pattern_breakout_up")) >= 1 and resistance_touches >= 2:
        long_score += 1.0 + min(max(breakout_distance, 0.0), 1.0) * 0.4
        reasons.append("pattern:range_breakout_up")
        if volume_z >= 1.0:
            long_score += 0.4
            reasons.append("pattern:volume_confirm_up")
    if _num(row.get(f"{p}pattern_breakout_down")) >= 1 and support_touches >= 2:
        short_score += 1.0 + min(max(breakout_distance, 0.0), 1.0) * 0.4
        reasons.append("pattern:range_breakout_down")
        if volume_z >= 1.0:
            short_score += 0.4
            reasons.append("pattern:volume_confirm_down")

    if _num(row.get(f"{p}pattern_retest_long")) >= 1:
        long_score += 1.1
        reasons.append("pattern:retest_long")
    if _num(row.get(f"{p}pattern_retest_short")) >= 1:
        short_score += 1.1
        reasons.append("pattern:retest_short")

    if _num(row.get(f"{p}pattern_wick_break_up")) >= 1:
        short_score += 0.8
        reasons.append("pattern:failed_breakout_up")
    if _num(row.get(f"{p}pattern_wick_break_down")) >= 1:
        long_score += 0.8
        reasons.append("pattern:failed_breakdown")

    if _num(row.get(f"{p}pattern_ascending_triangle")) >= 1:
        long_score += 0.4
        reasons.append("pattern:ascending_triangle")
    if _num(row.get(f"{p}pattern_descending_triangle")) >= 1:
        short_score += 0.4
        reasons.append("pattern:descending_triangle")
    if _num(row.get(f"{p}pattern_symmetric_triangle")) >= 1:
        reasons.append("pattern:symmetric_triangle")

    diff = long_score - short_score
    if diff >= 0.75:
        bias = 1
    elif diff <= -0.75:
        bias = -1
    else:
        bias = 0
    return {
        f"{p}pattern_score_long": round(float(long_score), 4),
        f"{p}pattern_score_short": round(float(short_score), 4),
        f"{p}pattern_bias": int(bias),
        f"{p}pattern_confidence": round(float(abs(diff)), 4),
        f"{p}pattern_reasons": "|".join(reasons),
    }
