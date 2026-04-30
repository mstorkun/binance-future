"""
Rule-based candlestick and price-action context.

The module converts visual chart-pattern ideas into deterministic OHLCV rules.
It uses only current and prior candles and does not issue standalone trades.
"""
from __future__ import annotations

import pandas as pd

import config


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    return num / den.replace(0, pd.NA)


def _dir_series(bullish: pd.Series, bearish: pd.Series) -> pd.Series:
    out = pd.Series(0, index=bullish.index, dtype="int64")
    out = out.mask(bullish, 1)
    out = out.mask(bearish, -1)
    return out


def add_pattern_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Append deterministic pattern columns using only current/prior bars."""
    if not getattr(config, "PATTERN_SIGNALS_ENABLED", True):
        return df

    out = df.copy()
    open_ = out["open"]
    high = out["high"]
    low = out["low"]
    close = out["close"]
    volume = out["volume"]

    candle_range = (high - low).replace(0, pd.NA)
    body = (close - open_).abs()
    upper_wick = high - pd.concat([open_, close], axis=1).max(axis=1)
    lower_wick = pd.concat([open_, close], axis=1).min(axis=1) - low
    body_pct = _safe_div(body, candle_range)
    upper_wick_pct = _safe_div(upper_wick, candle_range)
    lower_wick_pct = _safe_div(lower_wick, candle_range)
    vol_ref = out["volume_ma"] if "volume_ma" in out.columns else volume.rolling(20).mean()
    vol_ratio = _safe_div(volume, vol_ref)

    out["pattern_body_pct"] = body_pct
    out["pattern_upper_wick_pct"] = upper_wick_pct
    out["pattern_lower_wick_pct"] = lower_wick_pct
    out["pattern_volume_ratio"] = vol_ratio

    wick_body_ratio = getattr(config, "PATTERN_WICK_BODY_RATIO", 2.0)
    min_wick_pct = getattr(config, "PATTERN_MIN_WICK_RANGE_PCT", 0.45)
    bullish_wick = (
        (lower_wick >= body * wick_body_ratio)
        & (lower_wick_pct >= min_wick_pct)
        & (close > open_)
    )
    bearish_wick = (
        (upper_wick >= body * wick_body_ratio)
        & (upper_wick_pct >= min_wick_pct)
        & (close < open_)
    )
    out["pattern_wick_rejection"] = _dir_series(bullish_wick, bearish_wick)

    lookback = getattr(config, "PATTERN_SWEEP_LOOKBACK", 20)
    prev_low = low.rolling(lookback).min().shift(1)
    prev_high = high.rolling(lookback).max().shift(1)
    vol_ok = vol_ratio >= getattr(config, "PATTERN_VOLUME_MULT", 1.20)
    bullish_sweep = (
        (low < prev_low)
        & (close > prev_low)
        & (lower_wick_pct >= min_wick_pct)
        & vol_ok
    )
    bearish_sweep = (
        (high > prev_high)
        & (close < prev_high)
        & (upper_wick_pct >= min_wick_pct)
        & vol_ok
    )
    out["pattern_liquidity_sweep"] = _dir_series(bullish_sweep, bearish_sweep)

    atr = out["atr"] if "atr" in out.columns else None
    impulse_body_pct = getattr(config, "PATTERN_IMPULSE_BODY_PCT", 0.65)
    impulse_atr_mult = getattr(config, "PATTERN_IMPULSE_ATR_MULT", 1.15)
    if atr is not None:
        range_ok = (high - low) >= atr * impulse_atr_mult
    else:
        range_ok = pd.Series(False, index=out.index)
    bullish_impulse = (
        (close > open_)
        & (body_pct >= impulse_body_pct)
        & (upper_wick_pct <= 0.25)
        & range_ok
        & vol_ok
    )
    bearish_impulse = (
        (close < open_)
        & (body_pct >= impulse_body_pct)
        & (lower_wick_pct <= 0.25)
        & range_ok
        & vol_ok
    )
    out["pattern_impulse"] = _dir_series(bullish_impulse, bearish_impulse)

    prev_open = open_.shift(1)
    prev_close = close.shift(1)
    prev_body = body.shift(1)
    bullish_engulf = (
        (prev_close < prev_open)
        & (close > open_)
        & (open_ <= prev_close)
        & (close >= prev_open)
        & (body >= prev_body)
    )
    bearish_engulf = (
        (prev_close > prev_open)
        & (close < open_)
        & (open_ >= prev_close)
        & (close <= prev_open)
        & (body >= prev_body)
    )
    out["pattern_engulfing"] = _dir_series(bullish_engulf, bearish_engulf)

    prev_inside = (high.shift(1) < high.shift(2)) & (low.shift(1) > low.shift(2))
    bullish_inside_break = prev_inside & (close > high.shift(1)) & vol_ok
    bearish_inside_break = prev_inside & (close < low.shift(1)) & vol_ok
    out["pattern_inside_breakout"] = _dir_series(bullish_inside_break, bearish_inside_break)

    long_score = (
        (out["pattern_liquidity_sweep"] == 1).astype(float) * 1.00
        + (out["pattern_wick_rejection"] == 1).astype(float) * 0.60
        + (out["pattern_impulse"] == 1).astype(float) * 0.80
        + (out["pattern_engulfing"] == 1).astype(float) * 0.45
        + (out["pattern_inside_breakout"] == 1).astype(float) * 0.60
    )
    short_score = (
        (out["pattern_liquidity_sweep"] == -1).astype(float) * 1.00
        + (out["pattern_wick_rejection"] == -1).astype(float) * 0.60
        + (out["pattern_impulse"] == -1).astype(float) * 0.80
        + (out["pattern_engulfing"] == -1).astype(float) * 0.45
        + (out["pattern_inside_breakout"] == -1).astype(float) * 0.60
    )
    threshold = getattr(config, "PATTERN_CONFIRM_THRESHOLD", 0.80)
    bias = pd.Series(0, index=out.index, dtype="int64")
    bias = bias.mask((long_score >= threshold) & (long_score > short_score), 1)
    bias = bias.mask((short_score >= threshold) & (short_score > long_score), -1)

    out["pattern_score_long"] = long_score
    out["pattern_score_short"] = short_score
    out["pattern_bias"] = bias
    return out
