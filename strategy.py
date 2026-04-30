"""
Strateji: Donchian breakout + hacim filtresi + 1D EMA trend filtresi.

Kontrat (bot.py, backtest.py, optimize.py, walk_forward.py bu API'yi kullanır):
    LONG, SHORT, NONE                              — sinyal sabitleri
    get_signal(df) -> "long" | "short" | None      — yeni pozisyon sinyali
    check_exit(df, side) -> bool                   — daha sıkı Donchian kanalı kırıldı mı?
    trailing_stop(entry, extreme, side) -> float   — kazancın %15'i geri, %85'i kilit

Pre-condition: indicators.add_indicators() df'e şu sütunları eklemiş olmalı:
    donchian_high, donchian_low,
    donchian_exit_high, donchian_exit_low,
    volume, volume_ma, atr, rsi, daily_trend (opsiyonel)

Sinyal mantığı:
    LONG  : 4H high son N-bar Donchian high'ı kırdı (yukarı breakout)
            + bar hacmi >= 1.5 × ortalama
            + RSI <= 75 (aşırı alım değil)
            + daily_trend = 1 (varsa; yoksa filtre yok)
    SHORT : 4H low  son N-bar Donchian low'ı kırdı (aşağı breakdown)
            + bar hacmi >= 1.5 × ortalama
            + RSI >= 25 (aşırı satım değil)
            + daily_trend = -1
"""

import pandas as pd
import config

LONG  = "long"
SHORT = "short"
NONE  = None

TRAIL_GIVEBACK = 0.15


def _last_closed(df: pd.DataFrame) -> pd.Series:
    """Son kapanan bar (-2). Live botta -1 henüz kapanmamış olabilir."""
    return df.iloc[-2]


def _trend_signal(bar) -> str | None:
    """Klasik Donchian breakout (trend rejiminde)."""
    vol_ok      = bar["volume"] >= bar["volume_ma"] * config.VOLUME_MULT
    daily_trend = bar.get("daily_trend")
    has_daily   = pd.notna(daily_trend)

    long_break    = bar["close"] > bar["donchian_high"]
    rsi_long_ok   = bar["rsi"] <= config.RSI_MAX_LONG
    daily_long_ok = (not has_daily) or (daily_trend == 1)
    if long_break and vol_ok and rsi_long_ok and daily_long_ok:
        return LONG

    short_break    = bar["close"] < bar["donchian_low"]
    rsi_short_ok   = bar["rsi"] >= config.RSI_MIN_SHORT
    daily_short_ok = (not has_daily) or (daily_trend == -1)
    if short_break and vol_ok and rsi_short_ok and daily_short_ok:
        return SHORT
    return NONE


def _mean_reversion_signal(bar) -> str | None:
    """
    Range rejiminde mean reversion: aşırı RSI seviyelerinden ters yön.
    Sadece daily_trend ile uyumluysa al (daily long ise long sinyal, vb.)
    """
    rsi = bar["rsi"]
    daily_trend = bar.get("daily_trend")
    has_daily   = pd.notna(daily_trend)

    # Aşırı satım → LONG (sadece daily long veya nötr ortamda)
    if rsi <= 25 and ((not has_daily) or daily_trend == 1):
        return LONG
    # Aşırı alım → SHORT (sadece daily short veya nötr ortamda)
    if rsi >= 75 and ((not has_daily) or daily_trend == -1):
        return SHORT
    return NONE


def get_signal(df: pd.DataFrame) -> str | None:
    """
    Hibrit sinyal — rejime göre farklı strateji:
    - regime == "trend"  → Donchian breakout
    - regime == "range"  → Mean reversion (RSI extremes)
    - regime == "mixed"  → Trend sinyali (daha temkinli)
    """
    if len(df) < 3:
        return NONE

    bar = _last_closed(df)

    required = ("donchian_high", "donchian_low", "volume_ma", "rsi", "adx", "regime")
    if any(pd.isna(bar.get(col)) if col != "regime" else not isinstance(bar.get(col), str)
           for col in required):
        return NONE

    regime = bar["regime"]

    if regime == "range":
        return _mean_reversion_signal(bar)

    # trend veya mixed
    if bar["adx"] < config.ADX_THRESH:
        return NONE
    return _trend_signal(bar)


def check_exit(df: pd.DataFrame, side: str) -> bool:
    """
    Erken trend dönüş çıkışı: daha sıkı (10-bar) Donchian kanalı kırılırsa çık.
    Long pozisyon → close < donchian_exit_low
    Short pozisyon → close > donchian_exit_high
    """
    if len(df) < 2:
        return False
    bar = _last_closed(df)

    if side == LONG:
        ref = bar.get("donchian_exit_low")
        return pd.notna(ref) and bar["close"] < ref
    else:
        ref = bar.get("donchian_exit_high")
        return pd.notna(ref) and bar["close"] > ref


def trailing_stop(entry: float, extreme: float, side: str) -> float:
    """
    Long  : extreme - (extreme - entry) * TRAIL_GIVEBACK
    Short : extreme + (entry - extreme) * TRAIL_GIVEBACK
    """
    gain = abs(extreme - entry)
    if gain <= 0:
        return entry
    if side == LONG:
        return extreme - gain * TRAIL_GIVEBACK
    return extreme + gain * TRAIL_GIVEBACK
