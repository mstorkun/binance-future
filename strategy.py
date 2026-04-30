import pandas as pd
import config

LONG  = "long"
SHORT = "short"
NONE  = None


def get_signal(df: pd.DataFrame) -> str | None:
    """Son kapanan muma göre sinyal üret. Henüz kapanmayan son mum kullanılmaz."""
    if len(df) < 3:
        return NONE

    prev = df.iloc[-2]   # son kapanan mum
    curr = df.iloc[-1]   # bir önceki mum (çapraz teyidi için)

    ema_cross_up   = prev["ema_fast"] > prev["ema_slow"] and curr["ema_fast"] <= curr["ema_slow"]
    ema_cross_down = prev["ema_fast"] < prev["ema_slow"] and curr["ema_fast"] >= curr["ema_slow"]

    trend_up   = prev["ema_fast"] > prev["ema_slow"]
    trend_down = prev["ema_fast"] < prev["ema_slow"]

    adx_ok  = prev["adx"] > config.ADX_THRESH
    rsi_long  = config.RSI_LONG_MIN  <= prev["rsi"] <= config.RSI_LONG_MAX
    rsi_short = config.RSI_SHORT_MIN <= prev["rsi"] <= config.RSI_SHORT_MAX

    if ema_cross_up and adx_ok and rsi_long:
        return LONG
    if ema_cross_down and adx_ok and rsi_short:
        return SHORT

    # Kesişim yoksa trend yönünde pozisyon devam sinyali (mevcut pozisyon için kullanılmaz,
    # sadece yeni giriş için kesişim aranır)
    return NONE
