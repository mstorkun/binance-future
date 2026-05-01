from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd

import config

log = logging.getLogger(__name__)


def record(event_type: str, **fields: Any) -> None:
    """Append one order lifecycle event as JSONL.

    This is best-effort telemetry. A write failure must never block emergency
    close or stop placement paths.
    """
    row = {
        "ts": pd.Timestamp.now(tz="UTC").isoformat(),
        "event_type": event_type,
        "symbol": fields.pop("symbol", getattr(config, "SYMBOL", "")),
        "testnet": bool(getattr(config, "TESTNET", True)),
        "live_trading_approved": bool(getattr(config, "LIVE_TRADING_APPROVED", False)),
        **fields,
    }
    path = Path(getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl"))
    try:
        if path.parent and str(path.parent) != ".":
            path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_clean(row), ensure_ascii=True, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except Exception as exc:
        log.warning(f"Order event telemetry yazilamadi: {exc}")


def extract_order_summary(order: dict | None) -> dict[str, Any]:
    if not order:
        return {}
    info = order.get("info") or {}
    return {
        "id": order.get("id") or info.get("orderId"),
        "client_order_id": order.get("clientOrderId") or info.get("clientOrderId"),
        "status": order.get("status") or info.get("status"),
        "type": order.get("type") or info.get("type") or info.get("origType"),
        "side": order.get("side") or info.get("side"),
        "amount": _num(order.get("amount")) or _num(info.get("origQty")),
        "filled": _num(order.get("filled")) or _num(info.get("executedQty")),
        "remaining": _num(order.get("remaining")),
        "average": _num(order.get("average")) or _num(info.get("avgPrice")),
        "price": _num(order.get("price")) or _num(info.get("price")),
        "stop_price": _num(order.get("stopPrice")) or _num(order.get("triggerPrice")) or _num(info.get("stopPrice")),
        "cost": _num(order.get("cost")) or _num(info.get("cumQuote")),
        "reduce_only": order.get("reduceOnly", info.get("reduceOnly")),
        "position_side": info.get("positionSide"),
        "raw_info": info,
    }


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
