"""
Strateji modülü — EMA + ADX + RSI tabanlı trend takip.

Kontrat (bot.py, backtest.py, optimize.py, walk_forward.py bu API'yi kullanır):
    LONG, SHORT, NONE                              — sinyal sabitleri
    get_signal(df) -> "long" | "short" | None      — yeni pozisyon sinyali
    check_exit(df, side) -> bool                   — trend tersine döndü mü?
    trailing_stop(entry, extreme, side) -> float   — kazancın %15'i geri, %85'i kilit

İndikatörler indicators.add_indicators() tarafından df'e eklenmiş olmalıdır
(ema_fast, ema_slow, adx, rsi, atr sütunları).
"""

import pandas as pd
import config

LONG  = "long"
SHORT = "short"
NONE  = None

TRAIL_GIVEBACK = 0.15   # kazancın %15'ini geri ver, %85'ini kilitle


def get_signal(df: pd.DataFrame) -> str | None:
    """
    Yeni pozisyon açma sinyali. Sadece kapanan barlar üzerinden çalışır:
    son bar (-1) henüz kapanmamış olabilir; -2 son kapanan bardır.

    LONG  : EMA_fast > EMA_slow ilk kez (önceki bar -3'te <=) + ADX > eşik + RSI long aralığı
    SHORT : EMA_fast < EMA_slow ilk kez (önceki bar -3'te >=) + ADX > eşik + RSI short aralığı
    """
    if len(df) < 3:
        return NONE

    prev  = df.iloc[-2]
    prev2 = df.iloc[-3]

    trend_up   = prev["ema_fast"] > prev["ema_slow"]
    trend_down = prev["ema_fast"] < prev["ema_slow"]
    flipped_up   = trend_up   and prev2["ema_fast"] <= prev2["ema_slow"]
    flipped_down = trend_down and prev2["ema_fast"] >= prev2["ema_slow"]

    adx_ok    = prev["adx"] > config.ADX_THRESH
    rsi_long  = config.RSI_LONG_MIN  <= prev["rsi"] <= config.RSI_LONG_MAX
    rsi_short = config.RSI_SHORT_MIN <= prev["rsi"] <= config.RSI_SHORT_MAX

    if flipped_up and adx_ok and rsi_long:
        return LONG
    if flipped_down and adx_ok and rsi_short:
        return SHORT
    return NONE


def check_exit(df: pd.DataFrame, side: str) -> bool:
    """Açık pozisyon için trend tersine döndü mü? Son kapanan barı kullanır."""
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    if side == LONG:
        return prev["ema_fast"] < prev["ema_slow"]
    return prev["ema_fast"] > prev["ema_slow"]


def trailing_stop(entry: float, extreme: float, side: str) -> float:
    """
    Trailing stop fiyatı:
      LONG  : extreme - (extreme - entry) * TRAIL_GIVEBACK
      SHORT : extreme + (entry - extreme) * TRAIL_GIVEBACK

    extreme: pozisyon süresince görülen en uç fiyat
             (long → en yüksek high; short → en düşük low)

    Henüz kâr yoksa entry döndürür (çağıran taraf bu durumu erken filtrelemeli).
    """
    gain = abs(extreme - entry)
    if gain <= 0:
        return entry
    if side == LONG:
        return extreme - gain * TRAIL_GIVEBACK
    return extreme + gain * TRAIL_GIVEBACK
