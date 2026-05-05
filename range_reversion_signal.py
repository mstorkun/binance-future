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


def h4_regime_features(df_4h: pd.DataFrame) -> pd.DataFrame:
    close = pd.to_numeric(df_4h["close"], errors="coerce")
    ema80 = close.ewm(span=80, adjust=False, min_periods=80).mean()
    slope = ema80.pct_change(5) * 100.0
    side = ((close > ema80) & (slope > 0)).astype(int) - ((close < ema80) & (slope < 0)).astype(int)
    return pd.DataFrame(
        {
            "h4_close": close,
            "h4_adx": _adx(df_4h),
            "h4_ema80": ema80,
            "h4_ema80_slope_pct": slope,
            "h4_side": side,
        },
        index=df_4h.index,
    ).replace([float("inf"), float("-inf")], pd.NA)


def hourly_reversion_features(
    df_1h: pd.DataFrame,
    *,
    lookbacks: tuple[int, ...] = (24, 48, 72),
) -> pd.DataFrame:
    df = df_1h.sort_index()
    close = pd.to_numeric(df["close"], errors="coerce")
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce")
    atr = _true_range(df).ewm(alpha=1.0 / 14.0, adjust=False).mean()
    vol_mean = volume.rolling(72, min_periods=24).mean()
    vol_std = volume.rolling(72, min_periods=24).std(ddof=0)
    returns = np.log(close / close.shift(1)).replace([float("inf"), float("-inf")], pd.NA)
    realized = returns.rolling(24 * 30, min_periods=24 * 7).std(ddof=1) * math.sqrt(24.0 * 365.0)

    out = pd.DataFrame(
        {
            "h1_close": close.shift(1),
            "h1_high": high.shift(1),
            "h1_low": low.shift(1),
            "h1_atr": atr.shift(1),
            "h1_rsi": _rsi(close).shift(1),
            "h1_volume_z": ((volume - vol_mean) / vol_std.replace(0, pd.NA)).shift(1),
            "realized_vol_30d": realized.shift(1),
        },
        index=df.index,
    )
    for lookback in lookbacks:
        period = int(lookback)
        min_periods = max(12, period // 3)
        mean = close.rolling(period, min_periods=min_periods).mean().shift(1)
        std = close.rolling(period, min_periods=min_periods).std(ddof=0).shift(1).replace(0, pd.NA)
        prefix = f"lb{period}"
        out[f"{prefix}_mean"] = mean
        out[f"{prefix}_close_z"] = (close.shift(1) - mean) / std
        out[f"{prefix}_low_z"] = (low.shift(1) - mean) / std
        out[f"{prefix}_high_z"] = (high.shift(1) - mean) / std
        out[f"{prefix}_band_width_pct"] = (std * 2.0) / mean.replace(0, pd.NA)
    return out.replace([float("inf"), float("-inf")], pd.NA)


def build_signal_frame(
    *,
    df_1h: pd.DataFrame,
    df_4h: pd.DataFrame,
    df_1d: pd.DataFrame,
    lookbacks: tuple[int, ...] = (24, 48, 72),
) -> pd.DataFrame:
    """Build a 1h entry frame from prior closed 1h/4h/1d bars only."""
    base = df_1h[["open", "high", "low", "close", "volume"]].copy().sort_index()
    base.columns = [f"entry_{col}" for col in base.columns]
    if not isinstance(base.index, pd.DatetimeIndex):
        raise TypeError("df_1h index must be a DatetimeIndex")

    hourly = hourly_reversion_features(df_1h, lookbacks=lookbacks)
    h4 = _available(h4_regime_features(df_4h), pd.Timedelta(hours=4), base.index)
    daily = _available(daily_trend_features(df_1d), pd.Timedelta(days=1), base.index)
    return base.join([hourly, h4, daily], how="left").replace([float("inf"), float("-inf")], pd.NA)


def signal_side_from_row(
    row: pd.Series,
    *,
    lookback: int,
    z_min: float = 1.5,
    rsi_low: float = 35.0,
    rsi_high: float = 65.0,
    h4_adx_max: float = 26.0,
    min_band_width_pct: float = 0.006,
    require_reclaim: bool = False,
    avoid_daily_opposite: bool = True,
) -> int:
    prefix = f"lb{int(lookback)}"
    h4_adx = _num(row.get("h4_adx"), 999.0)
    band_width = _num(row.get(f"{prefix}_band_width_pct"), 0.0)
    if h4_adx > float(h4_adx_max) or band_width < float(min_band_width_pct):
        return 0

    daily_side = int(_num(row.get("daily_side")))
    long_daily_ok = (daily_side >= 0) if avoid_daily_opposite else True
    short_daily_ok = (daily_side <= 0) if avoid_daily_opposite else True

    rsi = _num(row.get("h1_rsi"), 50.0)
    close_z = _num(row.get(f"{prefix}_close_z"), 0.0)
    low_z = _num(row.get(f"{prefix}_low_z"), 0.0)
    high_z = _num(row.get(f"{prefix}_high_z"), 0.0)

    if require_reclaim:
        long_extreme = low_z <= -float(z_min) and close_z > -float(z_min)
        short_extreme = high_z >= float(z_min) and close_z < float(z_min)
    else:
        long_extreme = close_z <= -float(z_min)
        short_extreme = close_z >= float(z_min)

    long_ok = long_daily_ok and rsi <= float(rsi_low) and long_extreme
    short_ok = short_daily_ok and rsi >= float(rsi_high) and short_extreme
    if long_ok and not short_ok:
        return 1
    if short_ok and not long_ok:
        return -1
    return 0
