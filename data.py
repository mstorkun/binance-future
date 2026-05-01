import ccxt
import pandas as pd
import config
import flow_data


def make_exchange() -> ccxt.Exchange:
    if not config.TESTNET and not getattr(config, "LIVE_TRADING_APPROVED", False):
        raise RuntimeError("Live trading is blocked. Set LIVE_TRADING_APPROVED=True only after all gates pass.")
    if not config.TESTNET:
        profile = live_profile_status()
        if not profile["ok"]:
            raise RuntimeError(f"Live trading is blocked by profile guard: {profile['reason']}")
        user_stream = user_data_stream_status()
        if not user_stream["ok"]:
            raise RuntimeError(f"Live trading is blocked by user-data stream gate: {user_stream['reason']}")

    params = {
        "apiKey": config.API_KEY,
        "secret": config.API_SECRET,
        "options": {
            "defaultType": "future",
            "adjustForTimeDifference": bool(getattr(config, "ADJUST_FOR_TIME_DIFFERENCE", True)),
            "recvWindow": int(getattr(config, "RECV_WINDOW_MS", 5000)),
        },
    }
    exchange = ccxt.binance(params)
    if config.TESTNET:
        exchange.set_sandbox_mode(True)
    return exchange


def live_profile_status() -> dict:
    if not getattr(config, "LIVE_PROFILE_GUARD_ENABLED", True):
        return {
            "ok": True,
            "guard_enabled": False,
            "profile": getattr(config, "RUNTIME_PROFILE_NAME", ""),
            "reason": "",
            "mismatches": [],
        }

    expected = dict(getattr(config, "LIVE_PROFILE", {}) or {})
    expected_name = expected.pop("name", "")
    actual = {key: getattr(config, key, None) for key in expected}
    mismatches = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if not _profile_value_equal(actual_value, expected_value):
            mismatches.append({
                "key": key,
                "actual": actual_value,
                "expected": expected_value,
            })
    return {
        "ok": not mismatches,
        "guard_enabled": True,
        "runtime_profile": getattr(config, "RUNTIME_PROFILE_NAME", ""),
        "required_live_profile": expected_name,
        "actual": actual,
        "expected": expected,
        "mismatches": mismatches,
        "reason": "" if not mismatches else "live_profile_mismatch",
    }


def _profile_value_equal(left, right) -> bool:
    if isinstance(right, float) or isinstance(left, float):
        try:
            return abs(float(left) - float(right)) < 1e-12
        except (TypeError, ValueError):
            return False
    return left == right


def user_data_stream_status() -> dict:
    required = bool(getattr(config, "USER_DATA_STREAM_REQUIRED_FOR_LIVE", True))
    ready = bool(getattr(config, "USER_DATA_STREAM_READY", False))
    return {
        "ok": (not required) or ready,
        "required_for_live": required,
        "ready": ready,
        "reason": "" if ((not required) or ready) else "user_data_stream_not_ready",
    }


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


def fetch_weekly_ohlcv(exchange: ccxt.Exchange, limit: int = 200) -> pd.DataFrame:
    raw = exchange.fetch_ohlcv(config.SYMBOL, config.WEEKLY_TIMEFRAME, limit=limit)
    return _ohlcv_to_df(raw)


def fetch_recent_flow(exchange: ccxt.Exchange, limit: int | None = None) -> flow_data.FlowFetchResult:
    return flow_data.fetch_recent_flow(
        exchange,
        config.SYMBOL,
        period=getattr(config, "FLOW_PERIOD", config.TIMEFRAME),
        limit=limit or getattr(config, "FLOW_HISTORY_LIMIT", 500),
    )


def fetch_balance(exchange: ccxt.Exchange) -> float:
    """Free (kullanılabilir) bakiye — yeni pozisyon açma karar için."""
    bal = exchange.fetch_balance()
    return float(bal["USDT"]["free"])


def fetch_equity(exchange: ccxt.Exchange) -> float:
    """
    Toplam equity = wallet balance + unrealized PnL.
    Günlük kayıp limit kontrolü için doğru metrik (free balance pozisyon
    açıkken margin'e gittiğinden yanıltıcı olur).
    """
    bal = exchange.fetch_balance()
    info = bal.get("info", {})
    # Binance Futures: totalWalletBalance + totalUnrealizedProfit
    total_wallet  = float(info.get("totalWalletBalance") or bal["USDT"].get("total") or 0)
    unrealized    = float(info.get("totalUnrealizedProfit") or 0)
    return total_wallet + unrealized


def fetch_open_positions(exchange: ccxt.Exchange) -> list:
    positions = exchange.fetch_positions([config.SYMBOL])
    return [p for p in positions if float(p.get("contracts") or 0) != 0]


def fetch_all_open_positions(exchange: ccxt.Exchange, symbols: list[str]) -> list:
    """Tüm sembollerde toplam açık pozisyon sayısı için."""
    positions = exchange.fetch_positions(symbols)
    return [p for p in positions if float(p.get("contracts") or 0) != 0]
