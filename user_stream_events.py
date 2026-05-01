from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import config
import order_events


ORDER_TRADE_UPDATE = "ORDER_TRADE_UPDATE"
TERMINAL_ORDER_STATUSES = {"FILLED", "CANCELED", "EXPIRED", "EXPIRED_IN_MATCH"}
STATE_REFRESH_EXECUTION_TYPES = {"TRADE", "CANCELED", "CALCULATED", "EXPIRED"}


@dataclass(frozen=True)
class UserOrderUpdate:
    event_time: int | None
    transaction_time: int | None
    symbol: str
    raw_symbol: str
    client_order_id: str
    side: str
    order_type: str
    original_order_type: str
    execution_type: str
    status: str
    order_id: str
    original_qty: float
    last_filled_qty: float
    accumulated_filled_qty: float
    last_filled_price: float
    average_price: float
    stop_price: float
    commission_asset: str
    commission: float
    order_trade_time: int | None
    trade_id: str
    reduce_only: bool
    position_side: str
    realized_profit: float
    price_protect: bool
    expiry_reason: str

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_ORDER_STATUSES

    @property
    def partial(self) -> bool:
        return self.status == "PARTIALLY_FILLED"

    @property
    def liquidation_or_adl(self) -> bool:
        cid = self.client_order_id.lower()
        return cid.startswith("autoclose-") or cid == "adl_autoclose" or cid.startswith("settlement_autoclose-")

    @property
    def requires_immediate_reconcile(self) -> bool:
        return (
            self.terminal
            or self.partial
            or self.execution_type in STATE_REFRESH_EXECUTION_TYPES
            or self.liquidation_or_adl
        )


def is_order_trade_update(event: dict[str, Any]) -> bool:
    return str(event.get("e") or "") == ORDER_TRADE_UPDATE and isinstance(event.get("o"), dict)


def parse_order_trade_update(event: dict[str, Any]) -> UserOrderUpdate:
    if not is_order_trade_update(event):
        raise ValueError("event is not ORDER_TRADE_UPDATE")
    order = event["o"]
    raw_symbol = str(order.get("s") or "")
    return UserOrderUpdate(
        event_time=_int_or_none(event.get("E")),
        transaction_time=_int_or_none(event.get("T")),
        symbol=_normalize_symbol(raw_symbol),
        raw_symbol=raw_symbol,
        client_order_id=str(order.get("c") or ""),
        side=str(order.get("S") or ""),
        order_type=str(order.get("o") or ""),
        original_order_type=str(order.get("ot") or order.get("o") or ""),
        execution_type=str(order.get("x") or ""),
        status=str(order.get("X") or ""),
        order_id=str(order.get("i") or ""),
        original_qty=_float(order.get("q")),
        last_filled_qty=_float(order.get("l")),
        accumulated_filled_qty=_float(order.get("z")),
        last_filled_price=_float(order.get("L")),
        average_price=_float(order.get("ap")),
        stop_price=_float(order.get("sp")),
        commission_asset=str(order.get("N") or ""),
        commission=_float(order.get("n")),
        order_trade_time=_int_or_none(order.get("T")),
        trade_id=str(order.get("t") or ""),
        reduce_only=bool(order.get("R")),
        position_side=str(order.get("ps") or ""),
        realized_profit=_float(order.get("rp")),
        price_protect=bool(order.get("pP")),
        expiry_reason=str(order.get("er") or ""),
    )


def record_order_trade_update(event: dict[str, Any]) -> UserOrderUpdate:
    update = parse_order_trade_update(event)
    order_events.record(
        "user_stream_order_update",
        symbol=update.symbol,
        raw_symbol=update.raw_symbol,
        event_time=update.event_time,
        transaction_time=update.transaction_time,
        client_order_id=update.client_order_id,
        order_id=update.order_id,
        side=update.side,
        order_type=update.order_type,
        original_order_type=update.original_order_type,
        execution_type=update.execution_type,
        status=update.status,
        original_qty=update.original_qty,
        last_filled_qty=update.last_filled_qty,
        accumulated_filled_qty=update.accumulated_filled_qty,
        last_filled_price=update.last_filled_price,
        average_price=update.average_price,
        stop_price=update.stop_price,
        commission_asset=update.commission_asset,
        commission=update.commission,
        order_trade_time=update.order_trade_time,
        trade_id=update.trade_id,
        reduce_only=update.reduce_only,
        position_side=update.position_side,
        realized_profit=update.realized_profit,
        price_protect=update.price_protect,
        expiry_reason=update.expiry_reason,
        terminal=update.terminal,
        partial=update.partial,
        liquidation_or_adl=update.liquidation_or_adl,
        requires_immediate_reconcile=update.requires_immediate_reconcile,
        raw_event=event,
    )
    return update


def _normalize_symbol(raw_symbol: str) -> str:
    normalized = raw_symbol.replace("/", "").split(":")[0].upper()
    for symbol in getattr(config, "SYMBOLS", []):
        if symbol.replace("/", "").split(":")[0].upper() == normalized:
            return symbol
    configured = getattr(config, "SYMBOL", "")
    if configured and configured.replace("/", "").split(":")[0].upper() == normalized:
        return configured
    if normalized.endswith("USDT") and len(normalized) > 4:
        return f"{normalized[:-4]}/USDT"
    return raw_symbol


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
