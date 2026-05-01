"""
Local paper/testnet operations status report.

This is a lightweight dashboard substitute for terminal use. It reads runtime
telemetry files and prints a compact status without placing orders.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

import account_safety
import config
import data
import paper_runtime


def _read_json(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _csv_tail(path: str, n: int = 5) -> pd.DataFrame:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(p).tail(n)


def build_status(include_exchange: bool = False) -> dict[str, Any]:
    heartbeat = _read_json(getattr(config, "PAPER_HEARTBEAT_FILE", "paper_heartbeat.json"))
    now = pd.Timestamp.now(tz="UTC")
    updated_at = heartbeat.get("updated_at")
    age_minutes = None
    stale = True
    if updated_at:
        ts = pd.Timestamp(updated_at)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        age_minutes = (now - ts).total_seconds() / 60.0
        stale = age_minutes > float(getattr(config, "OPS_HEARTBEAT_STALE_MINUTES", 180))

    equity_tail = _csv_tail(getattr(config, "PAPER_EQUITY_CSV", "paper_equity.csv"), 1)
    decisions_tail = _csv_tail(getattr(config, "PAPER_DECISIONS_CSV", "paper_decisions.csv"), 20)
    trades_tail = _csv_tail(getattr(config, "PAPER_TRADES_CSV", "paper_trades.csv"), 20)
    errors_tail = _csv_tail(getattr(config, "PAPER_ERRORS_CSV", "paper_errors.csv"), 20)

    last_equity = equity_tail.iloc[-1].to_dict() if not equity_tail.empty else {}
    actions = decisions_tail["action"].value_counts().to_dict() if "action" in decisions_tail else {}
    skips = decisions_tail["skipped_reason"].value_counts().to_dict() if "skipped_reason" in decisions_tail else {}

    status = {
        "run_tag": heartbeat.get("run_tag", getattr(config, "PAPER_RUN_TAG", "default")),
        "timeframe": heartbeat.get("timeframe", getattr(config, "TIMEFRAME", "")),
        "flow_period": heartbeat.get("flow_period", getattr(config, "FLOW_PERIOD", "")),
        "scaled_lookbacks": heartbeat.get(
            "scaled_lookbacks",
            bool(getattr(config, "PAPER_SCALED_LOOKBACKS", False)),
        ),
        "heartbeat_status": heartbeat.get("status", "missing"),
        "heartbeat_age_minutes": round(age_minutes, 2) if age_minutes is not None else None,
        "heartbeat_stale": stale,
        "paper_pid": heartbeat.get("pid"),
        "wallet": heartbeat.get("wallet", last_equity.get("wallet")),
        "equity": heartbeat.get("equity", last_equity.get("equity")),
        "open_positions": heartbeat.get("open_positions", last_equity.get("open_positions")),
        "recent_actions": actions,
        "recent_skips": {k: v for k, v in skips.items() if str(k) and str(k) != "nan"},
        "recent_closed_trades": int(len(trades_tail)),
        "recent_errors": int(len(errors_tail)),
        "live_trading_approved": bool(getattr(config, "LIVE_TRADING_APPROVED", False)),
        "testnet": bool(getattr(config, "TESTNET", True)),
    }
    if include_exchange:
        status["exchange_safety"] = _exchange_safety_status()
    return status


def _exchange_safety_status() -> dict[str, Any]:
    try:
        exchange = data.make_exchange()
        return account_safety.account_safety_status(exchange, list(getattr(config, "SYMBOLS", [])))
    except Exception as exc:
        return {
            "ok": False,
            "reason": f"exchange_safety_unavailable:{exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Print local paper/testnet telemetry status.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--tag", default="", help="Read isolated paper files for this run tag.")
    parser.add_argument("--exchange", action="store_true", help="Query Binance/testnet account safety state.")
    args = parser.parse_args()
    with paper_runtime.temporary_paper_runtime(tag=args.tag):
        status = build_status(include_exchange=args.exchange)
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
        return 0

    print("=== OPS STATUS ===")
    for key, value in status.items():
        print(f"{key}: {value}")
    return 1 if status.get("heartbeat_stale") else 0


if __name__ == "__main__":
    raise SystemExit(main())
