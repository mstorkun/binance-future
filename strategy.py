import pandas as pd
import config

LONG  = "long"
SHORT = "short"
NONE  = None

# Aynı trend yönünde tekrar giriş engellemek için son sinyal takibi
_last_signal = None


def get_signal(df: pd.DataFrame) -> str | None:
    global _last_signal

    if len(df) < 3:
        return NONE

    prev = df.iloc[-2]  # son kapanan mum

    trend_up   = prev["ema_fast"] > prev["ema_slow"]
    trend_down = prev["ema_fast"] < prev["ema_slow"]
    adx_ok     = prev["adx"] > config.ADX_THRESH
    rsi_long   = config.RSI_LONG_MIN  <= prev["rsi"] <= config.RSI_LONG_MAX
    rsi_short  = config.RSI_SHORT_MIN <= prev["rsi"] <= config.RSI_SHORT_MAX

    # Trend değişimi tespiti (bir önceki barda zıt trend vardı mı?)
    prev2 = df.iloc[-3]
    trend_flipped_up   = trend_up   and prev2["ema_fast"] <= prev2["ema_slow"]
    trend_flipped_down = trend_down and prev2["ema_fast"] >= prev2["ema_slow"]

    signal = NONE

    if trend_up and adx_ok and rsi_long:
        # Kesişim anında veya güçlü trend devamında giriş
        if trend_flipped_up or _last_signal != LONG:
            signal = LONG

    elif trend_down and adx_ok and rsi_short:
        if trend_flipped_down or _last_signal != SHORT:
            signal = SHORT

    if signal:
        _last_signal = signal

    return signal
