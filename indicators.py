import pandas as pd
import config


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # EMA
    df["ema_fast"] = df["close"].ewm(span=config.EMA_FAST, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=config.EMA_SLOW, adjust=False).mean()

    # ATR
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.ewm(span=config.ATR_PERIOD, adjust=False).mean()

    # RSI
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).ewm(span=config.RSI_PERIOD, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(span=config.RSI_PERIOD, adjust=False).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, 1e-10)))

    # ADX
    up   = df["high"].diff()
    down = -df["low"].diff()
    plus_dm  = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr14    = tr.ewm(span=config.ADX_PERIOD, adjust=False).mean()
    plus_di  = 100 * plus_dm.ewm(span=config.ADX_PERIOD, adjust=False).mean() / atr14
    minus_di = 100 * minus_dm.ewm(span=config.ADX_PERIOD, adjust=False).mean() / atr14
    dx       = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10))
    df["adx"] = dx.ewm(span=config.ADX_PERIOD, adjust=False).mean()

    return df.dropna()
