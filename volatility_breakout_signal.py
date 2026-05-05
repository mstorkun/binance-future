from __future__ import annotations

import math

import numpy as np
import pandas as pd


BREAKOUT_LOOKBACKS = (24, 48, 72)
SQUEEZE_LOOKBACKS = (120, 240)


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


def _rolling_rank_pct(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(int(window), min_periods=max(30, int(window) // 4)).rank(pct=True)


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


def h4_context_features(df_4h: pd.DataFrame) -> pd.DataFrame:
    close = pd.to_numeric(df_4h["close"], errors="coerce")
    ema21 = close.ewm(span=21, adjust=False, min_periods=21).mean()
    ema55 = close.ewm(span=55, adjust=False, min_periods=55).mean()
    side = (ema21 > ema55).astype(int) - (ema21 < ema55).astype(int)
    return pd.DataFrame(
        {
            "h4_close": close,
            "h4_ema21": ema21,
            "h4_ema55": ema55,
            "h4_side": side,
            "h4_adx": _adx(df_4h),
        },
        index=df_4h.index,
    ).replace([float("inf"), float("-inf")], pd.NA)


def btc_context_features(df_btc_1h: pd.DataFrame) -> pd.DataFrame:
    close = pd.to_numeric(df_btc_1h["close"], errors="coerce")
    ema50 = close.ewm(span=50, adjust=False, min_periods=50).mean()
    ema200 = close.ewm(span=200, adjust=False, min_periods=200).mean()
    ret_4h = close.pct_change(4)
    returns = np.log(close / close.shift(1)).replace([float("inf"), float("-inf")], pd.NA)
    side = ((close > ema50) & (ema50 > ema200) & (ret_4h > 0)).astype(int) - (
        (close < ema50) & (ema50 < ema200) & (ret_4h < 0)
    ).astype(int)
    shock = returns / returns.rolling(72, min_periods=24).std(ddof=1).replace(0, pd.NA)
    vol_72h = returns.rolling(72, min_periods=24).std(ddof=1) * math.sqrt(24.0 * 365.0)
    return pd.DataFrame(
        {
            "btc_close": close,
            "btc_ema50": ema50,
            "btc_ema200": ema200,
            "btc_ret_4h": ret_4h,
            "btc_side": side,
            "btc_shock_z": shock,
            "btc_vol_72h": vol_72h,
        },
        index=df_btc_1h.index,
    ).replace([float("inf"), float("-inf")], pd.NA)


def h1_breakout_features(
    df_1h: pd.DataFrame,
    *,
    breakout_lookbacks: tuple[int, ...] = BREAKOUT_LOOKBACKS,
    squeeze_lookbacks: tuple[int, ...] = SQUEEZE_LOOKBACKS,
) -> pd.DataFrame:
    close = pd.to_numeric(df_1h["close"], errors="coerce")
    high = pd.to_numeric(df_1h["high"], errors="coerce")
    low = pd.to_numeric(df_1h["low"], errors="coerce")
    volume = pd.to_numeric(df_1h["volume"], errors="coerce")
    atr = _true_range(df_1h).ewm(alpha=1.0 / 14.0, adjust=False).mean()
    atr_safe = atr.replace(0, pd.NA)
    vol_mean = volume.rolling(72, min_periods=18).mean()
    vol_std = volume.rolling(72, min_periods=18).std(ddof=0)
    mid = close.rolling(20, min_periods=20).mean()
    std = close.rolling(20, min_periods=20).std(ddof=0)
    bb_width = (4.0 * std) / mid.replace(0, pd.NA)
    returns = np.log(close / close.shift(1)).replace([float("inf"), float("-inf")], pd.NA)
    realized = returns.rolling(720, min_periods=180).std(ddof=1) * math.sqrt(24.0 * 365.0)
    out = pd.DataFrame(
        {
            "h1_close": close,
            "h1_atr": atr,
            "h1_volume_z": (volume - vol_mean) / vol_std.replace(0, pd.NA),
            "h1_bb_width": bb_width,
            "realized_vol_30d": realized,
        },
        index=df_1h.index,
    )
    for squeeze_lookback in squeeze_lookbacks:
        pctile = _rolling_rank_pct(bb_width, int(squeeze_lookback))
        out[f"sq{squeeze_lookback}_bb_pctile"] = pctile
        out[f"sq{squeeze_lookback}_recent_squeeze"] = pctile.shift(1).rolling(24, min_periods=6).min()
    for breakout_lookback in breakout_lookbacks:
        period = int(breakout_lookback)
        min_periods = max(12, period // 2)
        prior_high = high.rolling(period, min_periods=min_periods).max().shift(1)
        prior_low = low.rolling(period, min_periods=min_periods).min().shift(1)
        prefix = f"bo{period}"
        out[f"{prefix}_high"] = prior_high
        out[f"{prefix}_low"] = prior_low
        out[f"{prefix}_range_atr"] = (prior_high - prior_low) / atr_safe
        out[f"{prefix}_up_atr"] = (close - prior_high) / atr_safe
        out[f"{prefix}_down_atr"] = (prior_low - close) / atr_safe
        out[f"{prefix}_breakout_up"] = (close > prior_high).astype(int)
        out[f"{prefix}_breakout_down"] = (close < prior_low).astype(int)
    return out.replace([float("inf"), float("-inf")], pd.NA)


def build_signal_frame(
    *,
    df_1h: pd.DataFrame,
    df_4h: pd.DataFrame,
    df_1d: pd.DataFrame,
    btc_1h: pd.DataFrame,
) -> pd.DataFrame:
    """Build a 1h-entry frame from closed 1h/4h/1d bars only."""
    base = df_1h[["open", "high", "low", "close", "volume"]].copy().sort_index()
    base.columns = [f"entry_{col}" for col in base.columns]
    if not isinstance(base.index, pd.DatetimeIndex):
        raise TypeError("df_1h index must be a DatetimeIndex")

    h1 = _available(h1_breakout_features(df_1h), pd.Timedelta(hours=1), base.index)
    h4 = _available(h4_context_features(df_4h), pd.Timedelta(hours=4), base.index)
    daily = _available(daily_trend_features(df_1d), pd.Timedelta(days=1), base.index)
    btc = _available(btc_context_features(btc_1h), pd.Timedelta(hours=1), base.index)
    btc_h4 = h4_context_features(btc_1h.resample("4h", label="left", closed="left").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    ).dropna(subset=["open", "high", "low", "close"]))
    btc_h4 = btc_h4.rename(columns={"h4_side": "btc_h4_side", "h4_adx": "btc_h4_adx"})[
        ["btc_h4_side", "btc_h4_adx"]
    ]
    btc_h4 = _available(btc_h4, pd.Timedelta(hours=4), base.index)
    return base.join([h1, h4, daily, btc, btc_h4], how="left").replace([float("inf"), float("-inf")], pd.NA)
