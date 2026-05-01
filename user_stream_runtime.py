from __future__ import annotations

from pathlib import Path
from typing import Any

import live_state
import order_events
import user_stream_events
import user_stream_reconcile


def handle_order_trade_update(event: dict[str, Any], *, state_path: str | Path | None = None) -> dict[str, Any]:
    """Parse, record, reconcile, and persist one ORDER_TRADE_UPDATE event."""
    update = user_stream_events.record_order_trade_update(event)
    positions = live_state.load_positions(state_path)
    new_positions, decision = user_stream_reconcile.apply_order_update_to_positions(positions, update)
    changed = new_positions != positions
    if changed:
        live_state.save_positions(new_positions, state_path)
    order_events.record(
        "user_stream_reconcile_decision",
        symbol=decision["symbol"],
        action=decision["action"],
        changed=changed,
        client_order_id=decision["client_order_id"],
        order_id=decision["order_id"],
        status=decision["status"],
        execution_type=decision["execution_type"],
        reduce_only=decision["reduce_only"],
        liquidation_or_adl=decision["liquidation_or_adl"],
        requires_immediate_reconcile=decision["requires_immediate_reconcile"],
    )
    return {
        "update": update,
        "decision": decision,
        "changed": changed,
        "positions": new_positions,
    }
