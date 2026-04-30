import pandas as pd
import pandas_ta as ta
import config


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # EMA
    df["ema_fast"] = ta.ema(df["close"], length=config.EMA_FAST)
    df["ema_slow"] = ta.ema(df["close"], length=config.EMA_SLOW)

    # ADX
    adx = ta.adx(df["high"], df["low"], df["close"], length=config.ADX_PERIOD)
    df["adx"] = adx[f"ADX_{config.ADX_PERIOD}"]

    # RSI
    df["rsi"] = ta.rsi(df["close"], length=config.RSI_PERIOD)

    # ATR
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=config.ATR_PERIOD)

    return df.dropna()
