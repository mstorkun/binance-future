from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
import pandas as pd

import hurst_gate


@dataclass(frozen=True)
class SignalRow:
    symbol: str
    timestamp: str
    side: str
    strength: float
    is_entry: bool
    gate_reasons: tuple[str, ...]


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


def _available(features: pd.DataFrame, delta: pd.Timedelta, index: pd.Index) -> pd.DataFrame:
    shifted = features.copy()
    shifted.index = shifted.index + delta
    return shifted.reindex(index, method="ffill")


def _timestamp_ns(index: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(index.view("int64"), index=index, dtype="float64")


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


def structure_4h_features(df_4h: pd.DataFrame, *, hurst_series: pd.Series | None = None) -> pd.DataFrame:
    close = pd.to_numeric(df_4h["close"], errors="coerce")
    ema21 = close.ewm(span=21, adjust=False, min_periods=21).mean()
    ema55 = close.ewm(span=55, adjust=False, min_periods=55).mean()
    side = (ema21 > ema55).astype(int) - (ema21 < ema55).astype(int)
    tr = _true_range(df_4h)
    atr = tr.ewm(alpha=1.0 / 14.0, adjust=False).mean()
    returns = np.log(close / close.shift(1)).replace([float("inf"), float("-inf")], pd.NA)
    if hurst_series is None:
        hurst_series = hurst_gate.rolling_hurst_dfa(returns, window=200)
    return pd.DataFrame(
        {
            "h4_close": close,
            "h4_ema21": ema21,
            "h4_ema55": ema55,
            "h4_ema_side": side,
            "h4_adx": _adx(df_4h),
            "h4_atr": atr,
            "h4_hurst": hurst_series.reindex(df_4h.index),
            "h4_hurst_regime": hurst_series.reindex(df_4h.index).apply(hurst_gate.regime_from_hurst),
        },
        index=df_4h.index,
    ).replace([float("inf"), float("-inf")], pd.NA)


def trigger_1h_features(df_1h: pd.DataFrame, *, donchian: int = 20, volume_window: int = 96) -> pd.DataFrame:
    close = pd.to_numeric(df_1h["close"], errors="coerce")
    high = pd.to_numeric(df_1h["high"], errors="coerce")
    low = pd.to_numeric(df_1h["low"], errors="coerce")
    volume = pd.to_numeric(df_1h["volume"], errors="coerce")
    prior_high = high.rolling(int(donchian), min_periods=max(5, int(donchian) // 2)).max().shift(1)
    prior_low = low.rolling(int(donchian), min_periods=max(5, int(donchian) // 2)).min().shift(1)
    vol_mean = volume.rolling(int(volume_window), min_periods=max(10, int(volume_window) // 4)).mean()
    vol_std = volume.rolling(int(volume_window), min_periods=max(10, int(volume_window) // 4)).std(ddof=0)
    volume_z = (volume - vol_mean) / vol_std.replace(0, pd.NA)
    long_break = close > prior_high
    short_break = close < prior_low
    out = pd.DataFrame(
        {
            "h1_close": close,
            "h1_donchian_high": prior_high,
            "h1_donchian_low": prior_low,
            "h1_volume_z": volume_z,
            "h1_breakout_long": long_break.astype(int),
            "h1_breakout_short": short_break.astype(int),
        },
        index=df_1h.index,
    )
    ns = _timestamp_ns(df_1h.index)
    out["h1_last_long_trigger_ns"] = ns.where(long_break).ffill()
    out["h1_last_short_trigger_ns"] = ns.where(short_break).ffill()
    out["h1_last_long_trigger_volume_z"] = volume_z.where(long_break).ffill()
    out["h1_last_short_trigger_volume_z"] = volume_z.where(short_break).ffill()
    out["h1_last_trigger_volume_z"] = volume_z.where(long_break | short_break).ffill()
    return out.replace([float("inf"), float("-inf")], pd.NA)


def realized_vol_features(df_1h: pd.DataFrame, *, window: int = 720) -> pd.DataFrame:
    close = pd.to_numeric(df_1h["close"], errors="coerce")
    returns = np.log(close / close.shift(1)).replace([float("inf"), float("-inf")], pd.NA)
    realized = returns.rolling(int(window), min_periods=max(24, int(window) // 4)).std(ddof=1) * math.sqrt(24.0 * 365.0)
    return pd.DataFrame({"realized_vol_30d": realized}, index=df_1h.index)


def build_signal_frame(
    *,
    df_1d: pd.DataFrame,
    df_4h: pd.DataFrame,
    df_1h: pd.DataFrame,
    symbol: str = "",
    hurst_series: pd.Series | None = None,
    hurst_min: float = 0.55,
    adx_min: float = 20.0,
    volume_z_min: float = 1.5,
    trigger_max_age_hours: float = 4.0,
) -> pd.DataFrame:
    """Build a 4h-entry signal frame from closed daily/4h/1h bars only."""
    base = df_4h[["open", "high", "low", "close", "volume"]].copy().sort_index()
    base.columns = [f"entry_{col}" for col in base.columns]
    if not isinstance(base.index, pd.DatetimeIndex):
        raise TypeError("df_4h index must be a DatetimeIndex")

    daily = _available(daily_trend_features(df_1d), pd.Timedelta(days=1), base.index)
    h4 = _available(structure_4h_features(df_4h, hurst_series=hurst_series), pd.Timedelta(hours=4), base.index)
    h1 = _available(trigger_1h_features(df_1h), pd.Timedelta(hours=1), base.index)
    vol = _available(realized_vol_features(df_1h), pd.Timedelta(hours=1), base.index)
    out = base.join([daily, h4, h1, vol], how="left")

    now_ns = pd.Series(out.index.view("int64"), index=out.index, dtype="float64")
    out["h1_long_trigger_age_hours"] = (now_ns - pd.to_numeric(out["h1_last_long_trigger_ns"], errors="coerce")) / 3_600_000_000_000.0
    out["h1_short_trigger_age_hours"] = (now_ns - pd.to_numeric(out["h1_last_short_trigger_ns"], errors="coerce")) / 3_600_000_000_000.0
    out["symbol"] = symbol
    out["signal_side"] = out.apply(
        lambda row: signal_side_from_row(
            row,
            hurst_min=hurst_min,
            adx_min=adx_min,
            volume_z_min=volume_z_min,
            trigger_max_age_hours=trigger_max_age_hours,
        ),
        axis=1,
    )
    out["signal_strength"] = out.apply(signal_strength_from_row, axis=1)
    return out.replace([float("inf"), float("-inf")], pd.NA)


def signal_side_from_row(
    row: pd.Series,
    *,
    hurst_min: float = 0.55,
    adx_min: float = 20.0,
    volume_z_min: float = 1.5,
    trigger_max_age_hours: float = 4.0,
) -> int:
    daily_side = int(_num(row.get("daily_side")))
    h4_side = int(_num(row.get("h4_ema_side")))
    adx_ok = _num(row.get("h4_adx")) >= float(adx_min)
    hurst_ok = _num(row.get("h4_hurst")) >= float(hurst_min)
    long_volume_ok = _num(row.get("h1_last_long_trigger_volume_z")) >= float(volume_z_min)
    short_volume_ok = _num(row.get("h1_last_short_trigger_volume_z")) >= float(volume_z_min)
    long_recent = 0.0 <= _num(row.get("h1_long_trigger_age_hours"), 9999.0) <= float(trigger_max_age_hours)
    short_recent = 0.0 <= _num(row.get("h1_short_trigger_age_hours"), 9999.0) <= float(trigger_max_age_hours)
    if daily_side == 1 and h4_side == 1 and adx_ok and hurst_ok and long_volume_ok and long_recent:
        return 1
    if daily_side == -1 and h4_side == -1 and adx_ok and hurst_ok and short_volume_ok and short_recent:
        return -1
    return 0


def signal_strength_from_row(row: pd.Series) -> float:
    hurst = max(_num(row.get("h4_hurst"), 0.5) - 0.5, 0.0) * 4.0
    adx = min(max((_num(row.get("h4_adx")) - 20.0) / 25.0, 0.0), 1.0)
    trigger_volume_values = [
        _num(row.get("h1_last_long_trigger_volume_z"), float("nan")),
        _num(row.get("h1_last_short_trigger_volume_z"), float("nan")),
        _num(row.get("h1_last_trigger_volume_z"), float("nan")),
    ]
    finite_volume_values = [value for value in trigger_volume_values if math.isfinite(value)]
    trigger_volume = max(finite_volume_values) if finite_volume_values else 0.0
    vol = min(max((trigger_volume - 1.0) / 2.0, 0.0), 1.0)
    return round(float(min(1.0, hurst * 0.4 + adx * 0.35 + vol * 0.25)), 4)


def signal_reasons_from_row(
    row: pd.Series,
    *,
    side: str,
    hurst_min: float = 0.55,
    adx_min: float = 20.0,
    volume_z_min: float = 1.5,
    trigger_max_age_hours: float = 4.0,
) -> tuple[str, ...]:
    side_sign = 1 if side == "long" else -1
    reasons: list[str] = []
    if int(_num(row.get("daily_side"))) == side_sign:
        reasons.append("daily:ema200_aligned")
    else:
        reasons.append("daily:not_aligned")
    if int(_num(row.get("h4_ema_side"))) == side_sign:
        reasons.append("h4:ema21_55_aligned")
    else:
        reasons.append("h4:not_aligned")
    if _num(row.get("h4_adx")) >= float(adx_min):
        reasons.append("h4:adx_ok")
    else:
        reasons.append("h4:adx_low")
    if _num(row.get("h4_hurst")) >= float(hurst_min):
        reasons.append("hurst:trend")
    else:
        reasons.append("hurst:not_trend")
    age_col = "h1_long_trigger_age_hours" if side == "long" else "h1_short_trigger_age_hours"
    if 0.0 <= _num(row.get(age_col), 9999.0) <= float(trigger_max_age_hours):
        reasons.append("h1:donchian_breakout_recent")
    else:
        reasons.append("h1:no_recent_breakout")
    volume_col = "h1_last_long_trigger_volume_z" if side == "long" else "h1_last_short_trigger_volume_z"
    if _num(row.get(volume_col)) >= float(volume_z_min):
        reasons.append("h1:volume_confirmed")
    else:
        reasons.append("h1:volume_low")
    return tuple(reasons)


def row_to_signal(
    row: pd.Series,
    *,
    symbol: str = "",
    hurst_min: float = 0.55,
    adx_min: float = 20.0,
    volume_z_min: float = 1.5,
    trigger_max_age_hours: float = 4.0,
) -> SignalRow:
    side_value = signal_side_from_row(
        row,
        hurst_min=hurst_min,
        adx_min=adx_min,
        volume_z_min=volume_z_min,
        trigger_max_age_hours=trigger_max_age_hours,
    )
    side = "long" if side_value == 1 else ("short" if side_value == -1 else "wait")
    reasons = signal_reasons_from_row(
        row,
        side="long" if side == "wait" else side,
        hurst_min=hurst_min,
        adx_min=adx_min,
        volume_z_min=volume_z_min,
        trigger_max_age_hours=trigger_max_age_hours,
    )
    timestamp = row.name.isoformat() if hasattr(row.name, "isoformat") else str(row.name)
    return SignalRow(
        symbol=symbol or str(row.get("symbol", "")),
        timestamp=timestamp,
        side=side,
        strength=signal_strength_from_row(row),
        is_entry=side in {"long", "short"},
        gate_reasons=reasons,
    )


def compute_signal(symbol: str, df_1d: pd.DataFrame, df_4h: pd.DataFrame, df_1h: pd.DataFrame) -> SignalRow:
    frame = build_signal_frame(df_1d=df_1d, df_4h=df_4h, df_1h=df_1h, symbol=symbol)
    if frame.empty:
        return SignalRow(symbol=symbol, timestamp="", side="wait", strength=0.0, is_entry=False, gate_reasons=("empty_frame",))
    return row_to_signal(frame.iloc[-1], symbol=symbol)
