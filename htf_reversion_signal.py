from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    return pd.to_numeric(num / den.replace(0, pd.NA), errors="coerce")


def _true_range(df: pd.DataFrame) -> pd.Series:
    return pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr = _true_range(df)
    atr = tr.ewm(alpha=1.0 / float(period), adjust=False).mean()
    plus_di = _safe_div(100.0 * plus_dm.ewm(alpha=1.0 / float(period), adjust=False).mean(), atr)
    minus_di = _safe_div(100.0 * minus_dm.ewm(alpha=1.0 / float(period), adjust=False).mean(), atr)
    dx = _safe_div(100.0 * (plus_di - minus_di).abs(), plus_di + minus_di)
    return dx.ewm(alpha=1.0 / float(period), adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / float(period), adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / float(period), adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100.0 - (100.0 / (1.0 + rs))


def _available(features: pd.DataFrame, delta: pd.Timedelta, index: pd.Index) -> pd.DataFrame:
    shifted = features.copy()
    shifted.index = shifted.index + delta
    return shifted.reindex(index, method="ffill")


def daily_trend_features(df_1d: pd.DataFrame) -> pd.DataFrame:
    close = pd.to_numeric(df_1d["close"], errors="coerce")
    ema200 = close.ewm(span=200, adjust=False, min_periods=200).mean()
    slope = ema200.pct_change(5) * 100.0
    side = ((close > ema200) & (slope > 0)).astype(int) - ((close < ema200) & (slope < 0)).astype(int)
    return pd.DataFrame(
        {
            "daily_close": close,
            "daily_ema200": ema200,
            "daily_ema200_slope_pct": slope,
            "daily_side": side,
        },
        index=df_1d.index,
    ).replace([float("inf"), float("-inf")], pd.NA)


def realized_vol_features(df_4h: pd.DataFrame, *, window: int = 180) -> pd.DataFrame:
    close = pd.to_numeric(df_4h["close"], errors="coerce")
    returns = np.log(close / close.shift(1)).replace([float("inf"), float("-inf")], pd.NA)
    realized = returns.rolling(int(window), min_periods=max(24, int(window) // 4)).std(ddof=1) * math.sqrt(6.0 * 365.0)
    return pd.DataFrame({"realized_vol_30d": realized}, index=df_4h.index)


def level_reversion_features(df_4h: pd.DataFrame, *, level_lookbacks: tuple[int, ...] = (60, 120, 180)) -> pd.DataFrame:
    close = pd.to_numeric(df_4h["close"], errors="coerce")
    high = pd.to_numeric(df_4h["high"], errors="coerce")
    low = pd.to_numeric(df_4h["low"], errors="coerce")
    volume = pd.to_numeric(df_4h["volume"], errors="coerce")
    atr = _true_range(df_4h).ewm(alpha=1.0 / 14.0, adjust=False).mean()
    atr_safe = atr.replace(0, pd.NA)
    vol_mean = volume.rolling(48, min_periods=12).mean()
    vol_std = volume.rolling(48, min_periods=12).std(ddof=0)

    out = pd.DataFrame(
        {
            "h4_close": close,
            "h4_atr": atr,
            "h4_rsi": _rsi(close),
            "h4_adx": _adx(df_4h),
            "h4_volume_z": (volume - vol_mean) / vol_std.replace(0, pd.NA),
        },
        index=df_4h.index,
    )
    for lookback in level_lookbacks:
        period = int(lookback)
        min_periods = max(20, period // 3)
        support = low.rolling(period, min_periods=min_periods).min().shift(1)
        resistance = high.rolling(period, min_periods=min_periods).max().shift(1)
        prefix = f"lb{period}"
        out[f"{prefix}_support"] = support
        out[f"{prefix}_resistance"] = resistance
        out[f"{prefix}_support_gap_atr"] = (low - support) / atr_safe
        out[f"{prefix}_support_reclaim_atr"] = (close - support) / atr_safe
        out[f"{prefix}_resistance_gap_atr"] = (resistance - high) / atr_safe
        out[f"{prefix}_resistance_reclaim_atr"] = (resistance - close) / atr_safe
        out[f"{prefix}_range_width_atr"] = (resistance - support) / atr_safe
    return out.replace([float("inf"), float("-inf")], pd.NA)


def build_signal_frame(
    *,
    df_1d: pd.DataFrame,
    df_4h: pd.DataFrame,
    level_lookbacks: tuple[int, ...] = (60, 120, 180),
) -> pd.DataFrame:
    """Build a 4h-entry frame from closed 1d/4h bars only."""
    base = df_4h[["open", "high", "low", "close", "volume"]].copy().sort_index()
    base.columns = [f"entry_{col}" for col in base.columns]
    if not isinstance(base.index, pd.DatetimeIndex):
        raise TypeError("df_4h index must be a DatetimeIndex")

    daily = _available(daily_trend_features(df_1d), pd.Timedelta(days=1), base.index)
    levels = _available(level_reversion_features(df_4h, level_lookbacks=level_lookbacks), pd.Timedelta(hours=4), base.index)
    vol = _available(realized_vol_features(df_4h), pd.Timedelta(hours=4), base.index)
    return base.join([daily, levels, vol], how="left").replace([float("inf"), float("-inf")], pd.NA)


def signal_side_from_row(
    row: pd.Series,
    *,
    level_lookback: int,
    rsi_low: float = 30.0,
    rsi_high: float = 70.0,
    max_adx: float = 24.0,
    touch_atr_mult: float = 0.25,
    max_reclaim_atr: float = 1.50,
    min_range_atr: float = 3.0,
    volume_z_min: float = 0.0,
    avoid_daily_opposite: bool = True,
) -> int:
    prefix = f"lb{int(level_lookback)}"
    adx_ok = _num(row.get("h4_adx"), 999.0) <= float(max_adx)
    volume_ok = _num(row.get("h4_volume_z"), -999.0) >= float(volume_z_min)
    range_ok = _num(row.get(f"{prefix}_range_width_atr"), 0.0) >= float(min_range_atr)
    if not (adx_ok and volume_ok and range_ok):
        return 0

    daily_side = int(_num(row.get("daily_side")))
    long_daily_ok = (daily_side >= 0) if avoid_daily_opposite else True
    short_daily_ok = (daily_side <= 0) if avoid_daily_opposite else True

    support_gap = _num(row.get(f"{prefix}_support_gap_atr"), 999.0)
    support_reclaim = _num(row.get(f"{prefix}_support_reclaim_atr"), 999.0)
    resistance_gap = _num(row.get(f"{prefix}_resistance_gap_atr"), 999.0)
    resistance_reclaim = _num(row.get(f"{prefix}_resistance_reclaim_atr"), 999.0)
    rsi = _num(row.get("h4_rsi"), 50.0)

    long_ok = (
        long_daily_ok
        and rsi <= float(rsi_low)
        and support_gap <= float(touch_atr_mult)
        and 0.0 <= support_reclaim <= float(max_reclaim_atr)
    )
    short_ok = (
        short_daily_ok
        and rsi >= float(rsi_high)
        and resistance_gap <= float(touch_atr_mult)
        and 0.0 <= resistance_reclaim <= float(max_reclaim_atr)
    )
    if long_ok and not short_ok:
        return 1
    if short_ok and not long_ok:
        return -1
    return 0

