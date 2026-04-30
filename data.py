import ccxt
import pandas as pd
import config


def make_exchange() -> ccxt.Exchange:
    params = {
        "apiKey": config.API_KEY,
        "secret": config.API_SECRET,
        "options": {"defaultType": "future"},
    }
    exchange = ccxt.binance(params)
    if config.TESTNET:
        exchange.set_sandbox_mode(True)
    return exchange


def _ohlcv_to_df(raw: list) -> pd.DataFrame:
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df.astype(float)


def fetch_ohlcv(exchange: ccxt.Exchange, limit: int = config.WARMUP_BARS + 10) -> pd.DataFrame:
    raw = exchange.fetch_ohlcv(config.SYMBOL, config.TIMEFRAME, limit=limit)
    return _ohlcv_to_df(raw)


def fetch_daily_ohlcv(exchange: ccxt.Exchange, limit: int = 200) -> pd.DataFrame:
    """1D mum verisi — daily trend filtresi için."""
    raw = exchange.fetch_ohlcv(config.SYMBOL, config.DAILY_TIMEFRAME, limit=limit)
    return _ohlcv_to_df(raw)


def fetch_balance(exchange: ccxt.Exchange) -> float:
    bal = exchange.fetch_balance()
    return float(bal["USDT"]["free"])


def fetch_open_positions(exchange: ccxt.Exchange) -> list:
    positions = exchange.fetch_positions([config.SYMBOL])
    return [p for p in positions if float(p.get("contracts") or 0) != 0]
