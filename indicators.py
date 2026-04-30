import pandas as pd
import config


def _wilder(series: pd.Series, period: int) -> pd.Series:
    """Wilder smoothing — standart RSI/ATR/ADX hesaplaması (alpha = 1/period)."""
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # EMA — fiyat trend filtresi için klasik EMA (span)
    df["ema_fast"] = df["close"].ewm(span=config.EMA_FAST, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=config.EMA_SLOW, adjust=False).mean()

    # True Range
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)

    # ATR — Wilder
    df["atr"] = _wilder(tr, config.ATR_PERIOD)

    # RSI — Wilder
    delta = df["close"].diff()
    gain  = _wilder(delta.clip(lower=0), config.RSI_PERIOD)
    loss  = _wilder(-delta.clip(upper=0), config.RSI_PERIOD)
    rs    = gain / loss.replace(0, 1e-10)
    df["rsi"] = 100 - (100 / (1 + rs))

    # ADX — Wilder
    up   = df["high"].diff()
    down = -df["low"].diff()
    plus_dm  = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr_w    = _wilder(tr, config.ADX_PERIOD)
    plus_di  = 100 * _wilder(plus_dm, config.ADX_PERIOD) / atr_w
    minus_di = 100 * _wilder(minus_dm, config.ADX_PERIOD) / atr_w
    dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10)
    df["adx"] = _wilder(dx, config.ADX_PERIOD)

    return df.dropna()
