from __future__ import annotations

import math
from typing import Any

import pandas as pd


DEFAULT_LOOKBACK = 20
DEFAULT_CORR_LOOKBACK = 20


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    return num / den.replace(0, pd.NA)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _direction(open_: pd.Series, close: pd.Series) -> pd.Series:
    body_dir = (close - open_).apply(lambda value: 1 if value > 0 else (-1 if value < 0 else 0))
    close_dir = close.diff().apply(lambda value: 1 if value > 0 else (-1 if value < 0 else 0))
    return body_dir.where(body_dir != 0, close_dir).fillna(0).astype(int)


def add_candle_structure_features(
    df: pd.DataFrame,
    *,
    lookback: int = DEFAULT_LOOKBACK,
    corr_lookback: int = DEFAULT_CORR_LOOKBACK,
) -> pd.DataFrame:
    """Append closed-candle structure features without using future bars."""
    out = df.copy()
    open_ = pd.to_numeric(out["open"], errors="coerce")
    high = pd.to_numeric(out["high"], errors="coerce")
    low = pd.to_numeric(out["low"], errors="coerce")
    close = pd.to_numeric(out["close"], errors="coerce")
    volume = pd.to_numeric(out["volume"], errors="coerce")

    candle_range = (high - low).replace(0, pd.NA)
    body_signed = close - open_
    body_abs = body_signed.abs()
    upper_wick = high - pd.concat([open_, close], axis=1).max(axis=1)
    lower_wick = pd.concat([open_, close], axis=1).min(axis=1) - low
    atr = pd.to_numeric(out["atr"], errors="coerce") if "atr" in out.columns else candle_range.rolling(14).mean()
    atr = atr.replace(0, pd.NA)
    range_atr = _safe_div(candle_range, atr)
    body_atr = _safe_div(body_abs, atr)
    body_pct = _safe_div(body_abs, candle_range)
    upper_wick_pct = _safe_div(upper_wick, candle_range)
    lower_wick_pct = _safe_div(lower_wick, candle_range)
    close_location = _safe_div(close - low, candle_range)
    direction = _direction(open_, close)

    lookback = max(2, int(lookback))
    corr_lookback = max(3, int(corr_lookback))
    rolling_high = high.rolling(lookback).max()
    rolling_low = low.rolling(lookback).min()
    rolling_atr = atr.rolling(lookback, min_periods=max(2, lookback // 2)).median()
    rolling_range_atr = _safe_div(rolling_high - rolling_low, rolling_atr)
    density = lookback / rolling_range_atr.replace(0, pd.NA)
    compression = _safe_div(
        rolling_range_atr,
        rolling_range_atr.rolling(lookback * 3, min_periods=lookback).median(),
    )
    direction_consistency = direction.rolling(lookback, min_periods=max(2, lookback // 2)).sum().abs() / lookback
    returns = close.pct_change()
    return_autocorr = returns.rolling(corr_lookback, min_periods=max(3, corr_lookback // 2)).corr(returns.shift(1))
    volume_ratio = _safe_div(volume, volume.rolling(lookback, min_periods=max(2, lookback // 2)).median())
    range_volume_corr = range_atr.rolling(corr_lookback, min_periods=max(3, corr_lookback // 2)).corr(volume_ratio)
    prior_range_ref = range_atr.rolling(lookback, min_periods=max(2, lookback // 2)).median().shift(1)
    expansion = _safe_div(range_atr, prior_range_ref)

    out["candle_range_atr"] = range_atr
    out["candle_body_atr"] = body_atr
    out["candle_body_pct"] = body_pct
    out["candle_upper_wick_pct"] = upper_wick_pct
    out["candle_lower_wick_pct"] = lower_wick_pct
    out["candle_close_location"] = close_location
    out["candle_direction"] = direction
    out["candle_rolling_range_atr"] = rolling_range_atr
    out["candle_density"] = density
    out["candle_compression"] = compression
    out["candle_direction_consistency"] = direction_consistency
    out["candle_return_autocorr"] = return_autocorr
    out["candle_range_volume_corr"] = range_volume_corr
    out["candle_expansion"] = expansion

    scored = out.apply(score_candle_structure_row, axis=1, result_type="expand")
    for column in scored.columns:
        out[column] = scored[column]
    return out


def score_candle_structure_row(row: pd.Series) -> dict[str, Any]:
    """Score side-specific candle pressure from already-closed bar features."""
    long_score = 0.0
    short_score = 0.0
    reasons: list[str] = []

    direction = _num(row.get("candle_direction"))
    body_pct = _num(row.get("candle_body_pct"))
    body_atr = _num(row.get("candle_body_atr"))
    close_location = _num(row.get("candle_close_location"), 0.5)
    upper_wick_pct = _num(row.get("candle_upper_wick_pct"))
    lower_wick_pct = _num(row.get("candle_lower_wick_pct"))
    density = _num(row.get("candle_density"))
    compression = _num(row.get("candle_compression"), 1.0)
    consistency = _num(row.get("candle_direction_consistency"))
    autocorr = _num(row.get("candle_return_autocorr"))
    range_volume_corr = _num(row.get("candle_range_volume_corr"))
    expansion = _num(row.get("candle_expansion"), 1.0)

    if body_pct >= 0.55 and body_atr >= 0.45:
        if direction > 0 and close_location >= 0.65:
            long_score += 1.2
            reasons.append("body:bull_impulse")
        elif direction < 0 and close_location <= 0.35:
            short_score += 1.2
            reasons.append("body:bear_impulse")

    if lower_wick_pct >= 0.45 and close_location >= 0.55:
        long_score += 0.9
        reasons.append("wick:lower_rejection")
    if upper_wick_pct >= 0.45 and close_location <= 0.45:
        short_score += 0.9
        reasons.append("wick:upper_rejection")

    compressed_break = compression <= 0.85 and expansion >= 1.10 and density >= 2.0
    if compressed_break and direction > 0:
        long_score += 1.4
        reasons.append("density:bull_breakout")
    elif compressed_break and direction < 0:
        short_score += 1.4
        reasons.append("density:bear_breakout")

    persistent = consistency >= 0.45 and autocorr >= -0.05
    if persistent and direction > 0:
        long_score += 0.7
        reasons.append("corr:bull_persistence")
    elif persistent and direction < 0:
        short_score += 0.7
        reasons.append("corr:bear_persistence")

    if range_volume_corr >= 0.20 and expansion >= 1.0:
        if direction > 0:
            long_score += 0.5
            reasons.append("corr:volume_range_bull")
        elif direction < 0:
            short_score += 0.5
            reasons.append("corr:volume_range_bear")

    diff = long_score - short_score
    if diff >= 0.75:
        bias = 1
    elif diff <= -0.75:
        bias = -1
    else:
        bias = 0
    return {
        "candle_structure_score_long": round(long_score, 4),
        "candle_structure_score_short": round(short_score, 4),
        "candle_structure_bias": int(bias),
        "candle_structure_confidence": round(abs(diff), 4),
        "candle_structure_reasons": "|".join(reasons),
    }
