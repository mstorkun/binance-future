import ccxt
import pandas as pd
import config


def make_exchange() -> ccxt.Exchange:
    params = {
        "apiKey": config.API_KEY,
        "secret": config.API_SECRET,
        "options": {"defaultType": "future"},
    }
    if config.TESTNET:
        params["urls"] = {
            "api": {
                "public":  "https://testnet.binancefuture.com",
                "private": "https://testnet.binancefuture.com",
            }
        }
    exchange = ccxt.binance(params)
    exchange.set_sandbox_mode(config.TESTNET)
    return exchange


def fetch_ohlcv(exchange: ccxt.Exchange, limit: int = config.WARMUP_BARS + 10) -> pd.DataFrame:
    raw = exchange.fetch_ohlcv(config.SYMBOL, config.TIMEFRAME, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df.astype(float)


def fetch_balance(exchange: ccxt.Exchange) -> float:
    bal = exchange.fetch_balance()
    return float(bal["USDT"]["free"])


def fetch_open_positions(exchange: ccxt.Exchange) -> list:
    positions = exchange.fetch_positions([config.SYMBOL])
    return [p for p in positions if float(p["contracts"]) != 0]
