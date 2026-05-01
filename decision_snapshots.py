from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd

import config

log = logging.getLogger(__name__)


SNAPSHOT_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "volume_ma",
    "atr",
    "rsi",
    "adx",
    "regime",
    "daily_trend",
    "weekly_trend",
    "donchian_high",
    "donchian_low",
    "donchian_exit_high",
    "donchian_exit_low",
    "flow_fresh",
    "flow_taker_buy_ratio",
)


def build_entry_snapshot(
    *,
    symbol: str,
    timeframe: str,
    signal: str,
    bar,
    equity: float,
    free_balance: float,
    risk_base_balance: float,
    global_open_count: int,
    max_open_positions: int,
    base_risk: float,
    effective_risk: float,
    risk_multiplier: float,
    risk_reasons,
    price: float,
    atr: float,
    status: str = "candidate",
) -> dict[str, Any]:
    return {
        "ts": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": status,
        "symbol": symbol,
        "timeframe": timeframe,
        "testnet": bool(getattr(config, "TESTNET", True)),
        "live_trading_approved": bool(getattr(config, "LIVE_TRADING_APPROVED", False)),
        "signal": signal,
        "bar_time": _index_iso(bar),
        "bar": _bar_fields(bar),
        "equity": equity,
        "free_balance": free_balance,
        "risk_base_balance": risk_base_balance,
        "global_open_count": global_open_count,
        "max_open_positions": max_open_positions,
        "base_risk": base_risk,
        "effective_risk": effective_risk,
        "risk_multiplier": risk_multiplier,
        "risk_reasons": list(risk_reasons or ()),
        "price": price,
        "atr": atr,
    }


def attach_order_result(snapshot: dict[str, Any], result: dict | None) -> dict[str, Any]:
    out = dict(snapshot)
    out["status"] = "opened" if result else "open_failed"
    if result:
        out["result"] = {
            "side": result.get("side"),
            "entry": result.get("entry"),
            "size": result.get("size"),
            "sl": result.get("sl"),
            "hard_sl": result.get("hard_sl"),
            "liquidation_price": result.get("liquidation_price"),
            "atr": result.get("atr"),
            "sl_order_id": result.get("sl_order_id"),
            "entry_client_order_id": result.get("entry_client_order_id"),
            "sl_client_order_id": result.get("sl_client_order_id"),
        }
    else:
        out["result"] = {}
    return out


def write_snapshot(snapshot: dict[str, Any], path: str | None = None) -> None:
    target = Path(path or getattr(config, "TRADE_DECISION_SNAPSHOTS_JSONL", "trade_decisions.jsonl"))
    try:
        if target.parent and str(target.parent) != ".":
            target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_clean(snapshot), ensure_ascii=True, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except Exception as exc:
        log.warning(f"Trade decision snapshot yazilamadi: {exc}")


def _bar_fields(bar) -> dict[str, Any]:
    return {col: _get(bar, col) for col in SNAPSHOT_COLUMNS if _get(bar, col) is not None}


def _index_iso(bar) -> str:
    name = getattr(bar, "name", None)
    if name is None:
        return ""
    try:
        return pd.Timestamp(name).isoformat()
    except Exception:
        return str(name)


def _get(bar, key: str):
    try:
        value = bar.get(key)
    except AttributeError:
        try:
            value = bar[key]
        except Exception:
            return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)
