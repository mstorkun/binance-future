"""
Deterministic alert generation for local paper/testnet operations.

The first alert sink is append-only JSONL so alert behavior is easy to test and
can later feed Telegram, email, or another notification channel.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

import config


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _add(
    rows: list[dict[str, Any]],
    *,
    status: dict[str, Any],
    code: str,
    severity: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    rows.append(
        {
            "code": code,
            "severity": severity,
            "message": message,
            "run_tag": status.get("run_tag"),
            "details": details or {},
        }
    )


def build_alerts(status: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    heartbeat_status = str(status.get("heartbeat_status") or "missing")
    if heartbeat_status != "ok":
        _add(
            rows,
            status=status,
            code="heartbeat_not_ok",
            severity="critical",
            message="Runtime heartbeat is not healthy.",
            details={"heartbeat_status": heartbeat_status},
        )

    if bool(status.get("heartbeat_stale")):
        _add(
            rows,
            status=status,
            code="heartbeat_stale",
            severity="critical",
            message="Runtime heartbeat is stale.",
            details={"heartbeat_age_minutes": status.get("heartbeat_age_minutes")},
        )

    recent_errors = int(_to_float(status.get("recent_errors"), 0.0))
    if recent_errors > 0:
        _add(
            rows,
            status=status,
            code="recent_runtime_errors",
            severity="warning",
            message="Recent runtime errors were recorded.",
            details={"recent_errors": recent_errors},
        )

    exchange_safety = status.get("exchange_safety")
    if isinstance(exchange_safety, dict) and not bool(exchange_safety.get("ok")):
        _add(
            rows,
            status=status,
            code="exchange_safety_failed",
            severity="critical",
            message="Exchange account safety check failed.",
            details={"reason": exchange_safety.get("reason"), "exchange_safety": exchange_safety},
        )

    event = status.get("latest_order_event") or {}
    event_type = str(event.get("event_type") or "")
    if event_type.endswith("_error"):
        _add(
            rows,
            status=status,
            code="latest_order_event_error",
            severity="critical",
            message="Latest order lifecycle event is an error.",
            details={"event_type": event_type, "event": event},
        )
    elif event_type in {
        "entry_stop_missing_emergency_close",
        "post_fill_liquidation_guard_block",
        "post_fill_stop_missing",
    }:
        _add(
            rows,
            status=status,
            code="latest_order_event_guard",
            severity="critical",
            message="Latest order lifecycle event indicates a protective guard issue.",
            details={"event_type": event_type, "event": event},
        )

    open_positions = int(_to_float(status.get("open_positions"), 0.0))
    live_state_positions = int(_to_float(status.get("live_state_positions"), 0.0))
    compare_live_state = bool(status.get("compare_live_state_positions", False))
    if compare_live_state and (open_positions or live_state_positions) and open_positions != live_state_positions:
        _add(
            rows,
            status=status,
            code="state_position_mismatch",
            severity="warning",
            message="Runtime open position count differs from persisted live state.",
            details={
                "open_positions": open_positions,
                "live_state_positions": live_state_positions,
                "live_state_updated_at": status.get("live_state_updated_at"),
            },
        )

    if not bool(status.get("testnet", True)) and not bool(status.get("live_trading_approved", False)):
        _add(
            rows,
            status=status,
            code="live_gate_mismatch",
            severity="critical",
            message="Live mode is visible while live trading approval is false.",
            details={
                "testnet": status.get("testnet"),
                "live_trading_approved": status.get("live_trading_approved"),
            },
        )

    return rows


def write_alerts(alert_rows: list[dict[str, Any]], path: str | None = None) -> int:
    if not alert_rows:
        return 0

    target = Path(path or getattr(config, "ALERTS_JSONL", "alerts.jsonl"))
    if target.parent != Path("."):
        target.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    ts = pd.Timestamp.now(tz="UTC").isoformat()
    with target.open("a", encoding="utf-8") as handle:
        for row in alert_rows:
            payload = dict(row)
            payload.setdefault("ts", ts)
            handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")
            written += 1
        handle.flush()
        os.fsync(handle.fileno())
    return written
