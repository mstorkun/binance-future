import pandas as pd
import config

LONG  = "long"
SHORT = "short"
NONE  = None

TRAIL_GIVEBACK = 0.30  # kazancın %30'unu geri ver, %70'ini kilitle


def get_signal(df: pd.DataFrame) -> str | None:
    """Yeni pozisyon açma sinyali."""
    if len(df) < 3:
        return NONE

    prev  = df.iloc[-2]
    prev2 = df.iloc[-3]

    trend_up   = prev["ema_fast"] > prev["ema_slow"]
    trend_down = prev["ema_fast"] < prev["ema_slow"]
    adx_ok     = prev["adx"] > config.ADX_THRESH
    rsi_long   = config.RSI_LONG_MIN  <= prev["rsi"] <= config.RSI_LONG_MAX
    rsi_short  = config.RSI_SHORT_MIN <= prev["rsi"] <= config.RSI_SHORT_MAX

    # Sadece trend ilk oluştuğunda gir (kesişim anı)
    flipped_up   = trend_up   and prev2["ema_fast"] <= prev2["ema_slow"]
    flipped_down = trend_down and prev2["ema_fast"] >= prev2["ema_slow"]

    if flipped_up and adx_ok and rsi_long:
        return LONG
    if flipped_down and adx_ok and rsi_short:
        return SHORT
    return NONE


def check_exit(df: pd.DataFrame, side: str) -> bool:
    """Açık pozisyon için trend tersine döndü mü?"""
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    if side == LONG:
        return prev["ema_fast"] < prev["ema_slow"]
    else:
        return prev["ema_fast"] > prev["ema_slow"]


def trailing_stop(entry: float, highest: float, side: str) -> float:
    """
    Kazancın %30'unu geri ver, %70'ini kilitle.
    Long : trailing_sl = highest - (highest - entry) * 0.30
    Short: trailing_sl = lowest  + (entry - lowest) * 0.30
    """
    gain = abs(highest - entry)
    if gain <= 0:
        return entry  # henüz kârda değil, entry'yi koru

    if side == LONG:
        return highest - gain * TRAIL_GIVEBACK
    else:
        return highest + gain * TRAIL_GIVEBACK
