from __future__ import annotations

from typing import Any

import user_stream_events


def apply_order_update_to_positions(
    positions: dict[str, dict[str, Any]],
    update: user_stream_events.UserOrderUpdate,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Apply a parsed user-stream order update to local positions.

    This is deliberately conservative. It removes local state only when the
    exchange event clearly indicates a close-side condition that makes local
    trailing/SL state unsafe to keep.
    """
    out = {symbol: dict(pos) for symbol, pos in positions.items()}
    symbol = update.symbol
    action = "no_change"

    if _clear_position(update):
        out.pop(symbol, None)
        action = "remove_position"
    elif symbol in out:
        out[symbol]["last_user_stream_order_status"] = update.status
        out[symbol]["last_user_stream_execution_type"] = update.execution_type
        out[symbol]["last_user_stream_order_id"] = update.order_id
        out[symbol]["last_user_stream_client_order_id"] = update.client_order_id
        out[symbol]["last_user_stream_filled_qty"] = update.accumulated_filled_qty
        out[symbol]["last_user_stream_realized_profit"] = update.realized_profit
        action = "mark_position"

    return out, {
        "action": action,
        "symbol": symbol,
        "client_order_id": update.client_order_id,
        "order_id": update.order_id,
        "status": update.status,
        "execution_type": update.execution_type,
        "reduce_only": update.reduce_only,
        "liquidation_or_adl": update.liquidation_or_adl,
        "requires_immediate_reconcile": update.requires_immediate_reconcile,
    }


def _clear_position(update: user_stream_events.UserOrderUpdate) -> bool:
    if update.liquidation_or_adl:
        return True
    if update.reduce_only and update.status == "FILLED":
        return True
    if update.original_order_type in {"STOP_MARKET", "TAKE_PROFIT_MARKET"} and update.status == "FILLED":
        return True
    return False
