"""
İndikatör hesaplamaları — Wilder smoothing standart RSI/ADX/ATR için.

Pre-condition: df'de open, high, low, close, volume sütunları olmalı.
Post-condition: df'e şu sütunlar eklenir:
    ema_fast, ema_slow              — klasik EMA span
    atr                             — Wilder ATR
    rsi                             — Wilder RSI
    adx                             — Wilder ADX
    donchian_high, donchian_low     — N-bar rolling max/min (giriş)
    donchian_exit_high, ..._low     — daha sıkı rolling max/min (erken çıkış)
    volume_ma                       — N-bar volume ortalaması
    daily_trend                     — opsiyonel; data.py merge ettiyse 1/-1
"""

import pandas as pd
import config


def _wilder(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def _true_range(df: pd.DataFrame) -> pd.Series:
    return pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # --- EMA (klasik span) ---
    df["ema_fast"] = df["close"].ewm(span=config.EMA_FAST, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=config.EMA_SLOW, adjust=False).mean()

    # --- ATR (Wilder) ---
    tr = _true_range(df)
    df["atr"] = _wilder(tr, config.ATR_PERIOD)

    # --- RSI (Wilder) ---
    delta = df["close"].diff()
    gain  = _wilder(delta.clip(lower=0), config.RSI_PERIOD)
    loss  = _wilder(-delta.clip(upper=0), config.RSI_PERIOD)
    rs    = gain / loss.replace(0, 1e-10)
    df["rsi"] = 100 - (100 / (1 + rs))

    # --- ADX (Wilder) ---
    up   = df["high"].diff()
    down = -df["low"].diff()
    plus_dm  = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr_w    = _wilder(tr, config.ADX_PERIOD)
    plus_di  = 100 * _wilder(plus_dm, config.ADX_PERIOD) / atr_w
    minus_di = 100 * _wilder(minus_dm, config.ADX_PERIOD) / atr_w
    dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10)
    df["adx"] = _wilder(dx, config.ADX_PERIOD)

    # --- Donchian Channels ---
    # Mevcut barı dahil ETMEDEN önceki N barın max/min'i (look-ahead'i önlemek için shift)
    df["donchian_high"] = df["high"].rolling(config.DONCHIAN_PERIOD).max().shift(1)
    df["donchian_low"]  = df["low"].rolling(config.DONCHIAN_PERIOD).min().shift(1)
    df["donchian_exit_high"] = df["high"].rolling(config.DONCHIAN_EXIT).max().shift(1)
    df["donchian_exit_low"]  = df["low"].rolling(config.DONCHIAN_EXIT).min().shift(1)

    # --- Volume MA + OBV (volume direction) ---
    df["volume_ma"] = df["volume"].rolling(config.VOLUME_MA_PERIOD).mean()
    sign  = df["close"].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    df["obv"] = (sign * df["volume"]).cumsum()
    df["obv_ema"] = df["obv"].ewm(span=20, adjust=False).mean()

    # --- Bollinger Bandwidth (volatility regime) ---
    bb_period = 20
    sma  = df["close"].rolling(bb_period).mean()
    std  = df["close"].rolling(bb_period).std()
    df["bb_bw"] = (2 * 2 * std) / sma  # bandwidth ratio (~%)
    df["bb_bw_ma"] = df["bb_bw"].rolling(50).mean()

    # --- Regime Detection ---
    # 'trend'   : ADX > 25 ve BB bandwidth genişliyor
    # 'range'   : ADX < 18 ve bandwidth daralıyor
    # 'mixed'   : diğer
    cond_trend = (df["adx"] > 25) & (df["bb_bw"] > df["bb_bw_ma"])
    cond_range = (df["adx"] < 18) & (df["bb_bw"] < df["bb_bw_ma"])
    df["regime"] = "mixed"
    df.loc[cond_trend, "regime"] = "trend"
    df.loc[cond_range, "regime"] = "range"

    return df.dropna()


def add_daily_trend(df_4h: pd.DataFrame, df_1d: pd.DataFrame) -> pd.DataFrame:
    """
    1D EMA50 trendini 4H df'e merge et.
    daily_trend = 1  → 1D close > EMA50 (long-only ortam)
    daily_trend = -1 → 1D close < EMA50 (short-only ortam)
    """
    daily = df_1d.copy()
    daily["daily_ema"]   = daily["close"].ewm(span=config.DAILY_EMA_PERIOD, adjust=False).mean()
    daily["daily_trend"] = (daily["close"] > daily["daily_ema"]).map({True: 1, False: -1})

    # 4H zaman damgasına göre forward-fill (her 4H bar, son kapanan 1D barına bakar)
    daily_lookup = daily[["daily_trend"]].copy()
    daily_lookup.index = daily_lookup.index + pd.Timedelta(days=1)  # 1D bar kapanışı sonra geçerli

    df_out = df_4h.copy()
    df_out["daily_trend"] = daily_lookup["daily_trend"].reindex(df_out.index, method="ffill")
    return df_out
