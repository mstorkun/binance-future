from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def _clean_values(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    return arr


def _scales(length: int, *, min_scale: int = 8, max_scale: int | None = None, scale_count: int = 6) -> np.ndarray:
    if length < min_scale * 4:
        return np.array([], dtype=int)
    max_scale = int(max_scale or max(min(length // 4, 128), min_scale * 2))
    max_scale = min(max_scale, length // 2)
    if max_scale <= min_scale:
        return np.array([], dtype=int)
    scales = np.unique(np.logspace(math.log10(min_scale), math.log10(max_scale), int(scale_count)).astype(int))
    return scales[scales >= min_scale]


def hurst_dfa(values: np.ndarray, *, min_scale: int = 8, max_scale: int | None = None, scale_count: int = 6) -> float:
    """Estimate Hurst exponent with detrended fluctuation analysis.

    Input values are returns/increments. The profile is built internally, so the
    output can be used as a trend-regime gate without peeking at future bars.
    """
    arr = _clean_values(values)
    if len(arr) < int(min_scale) * 4:
        return float("nan")
    profile = np.cumsum(arr - np.mean(arr))
    used_scales: list[int] = []
    flucts: list[float] = []
    for scale in _scales(len(profile), min_scale=min_scale, max_scale=max_scale, scale_count=scale_count):
        segment_count = len(profile) // int(scale)
        if segment_count < 2:
            continue
        rms_values: list[float] = []
        x = np.arange(int(scale), dtype=float)
        for segment_idx in range(segment_count):
            segment = profile[segment_idx * int(scale) : (segment_idx + 1) * int(scale)]
            if len(segment) != int(scale):
                continue
            slope, intercept = np.polyfit(x, segment, 1)
            resid = segment - (slope * x + intercept)
            rms = math.sqrt(float(np.mean(resid * resid)))
            if math.isfinite(rms) and rms > 0:
                rms_values.append(rms)
        if rms_values:
            used_scales.append(int(scale))
            flucts.append(float(np.mean(rms_values)))
    if len(used_scales) < 3:
        return float("nan")
    slope, _ = np.polyfit(np.log(used_scales), np.log(flucts), 1)
    return float(slope) if math.isfinite(float(slope)) else float("nan")


def hurst_rs(values: np.ndarray, *, min_scale: int = 8, max_scale: int | None = None, scale_count: int = 6) -> float:
    """Estimate Hurst exponent with the classic rescaled-range sanity check."""
    arr = _clean_values(values)
    if len(arr) < int(min_scale) * 4:
        return float("nan")
    used_scales: list[int] = []
    rs_values: list[float] = []
    for scale in _scales(len(arr), min_scale=min_scale, max_scale=max_scale, scale_count=scale_count):
        segment_count = len(arr) // int(scale)
        if segment_count < 2:
            continue
        ratios: list[float] = []
        for segment_idx in range(segment_count):
            segment = arr[segment_idx * int(scale) : (segment_idx + 1) * int(scale)]
            centered = segment - np.mean(segment)
            cumulative = np.cumsum(centered)
            r = float(np.max(cumulative) - np.min(cumulative))
            s = float(np.std(segment, ddof=1))
            if r > 0 and s > 0 and math.isfinite(r / s):
                ratios.append(r / s)
        if ratios:
            used_scales.append(int(scale))
            rs_values.append(float(np.mean(ratios)))
    if len(used_scales) < 3:
        return float("nan")
    slope, _ = np.polyfit(np.log(used_scales), np.log(rs_values), 1)
    return float(slope) if math.isfinite(float(slope)) else float("nan")


def rolling_hurst_dfa(
    returns: pd.Series,
    *,
    window: int = 200,
    min_periods: int | None = None,
    min_scale: int = 8,
    max_scale: int | None = None,
    scale_count: int = 6,
) -> pd.Series:
    window = int(window)
    min_periods = int(min_periods or window)
    series = pd.to_numeric(returns, errors="coerce")
    return series.rolling(window, min_periods=min_periods).apply(
        lambda values: hurst_dfa(values, min_scale=min_scale, max_scale=max_scale, scale_count=scale_count),
        raw=True,
    )


def rolling_hurst_rs(
    returns: pd.Series,
    *,
    window: int = 200,
    min_periods: int | None = None,
    min_scale: int = 8,
    max_scale: int | None = None,
    scale_count: int = 6,
) -> pd.Series:
    window = int(window)
    min_periods = int(min_periods or window)
    series = pd.to_numeric(returns, errors="coerce")
    return series.rolling(window, min_periods=min_periods).apply(
        lambda values: hurst_rs(values, min_scale=min_scale, max_scale=max_scale, scale_count=scale_count),
        raw=True,
    )


def regime_from_hurst(value: Any, *, trend_threshold: float = 0.55, mean_revert_threshold: float = 0.45) -> str:
    try:
        hurst = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if not math.isfinite(hurst):
        return "unknown"
    if hurst >= float(trend_threshold):
        return "trend"
    if hurst <= float(mean_revert_threshold):
        return "anti_persistent"
    return "neutral"


def hurst_bias_audit_row() -> dict[str, Any]:
    return {
        "module": "hurst_gate",
        "lookahead_safe": True,
        "closed_bar_only": True,
        "feature": "rolling_hurst_dfa",
        "evidence": "rolling window uses current/past returns only; report shifts 4h features to next open before entry",
    }
