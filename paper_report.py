"""
Detailed paper telemetry report.

Reads local paper-runner files and summarizes the latest heartbeat, equity,
symbol decisions, skips, errors, and safety flags. This script never places
orders.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, deque
from pathlib import Path
from typing import Any

import pandas as pd

import config
import paper_runtime


DECISION_FIELDS = [
    "symbol",
    "action",
    "bar_time",
    "close",
    "signal",
    "regime",
    "adx",
    "rsi",
    "daily_trend",
    "weekly_trend",
    "risk_mult",
    "risk_block",
    "risk_reasons",
    "effective_risk_pct",
    "orderbook_ok",
    "orderbook_reason",
    "flow_fresh",
    "flow_bucket_age_minutes",
    "flow_snapshot_age_minutes",
]


def _read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _csv_tail(path: str | Path, limit: int) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return []
    rows: deque[dict[str, str]] = deque(maxlen=max(1, limit))
    with p.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return list(rows)


def _utc_age_minutes(value: str | None) -> float | None:
    if not value:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return (pd.Timestamp.now(tz="UTC") - ts).total_seconds() / 60.0


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped and stripped.lower() != "nan" else None
    return value


def _maybe_float(value: Any) -> float | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compact_decision(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    float_fields = {
        "close",
        "adx",
        "rsi",
        "risk_mult",
        "effective_risk_pct",
        "flow_bucket_age_minutes",
        "flow_snapshot_age_minutes",
    }
    for field in DECISION_FIELDS:
        value = row.get(field)
        out[field] = _maybe_float(value) if field in float_fields else _clean(value)
    return out


def _compact_position(symbol: str, pos: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "side": _clean(pos.get("side")),
        "entry_time": _clean(pos.get("entry_time")),
        "entry": _maybe_float(pos.get("entry")),
        "size": _maybe_float(pos.get("size")),
        "notional": _maybe_float(pos.get("notional")),
        "sl": _maybe_float(pos.get("sl")),
        "hard_sl": _maybe_float(pos.get("hard_sl")),
        "risk_pct": _maybe_float(pos.get("risk_pct")),
        "risk_mult": _maybe_float(pos.get("risk_mult")),
        "risk_reasons": _clean(pos.get("risk_reasons")),
        "max_favorable": _maybe_float(pos.get("max_favorable")),
        "max_adverse": _maybe_float(pos.get("max_adverse")),
        "max_favorable_pct": _maybe_float(pos.get("max_favorable_pct")),
        "max_adverse_pct": _maybe_float(pos.get("max_adverse_pct")),
    }


def _compact_trade(row: dict[str, Any]) -> dict[str, Any]:
    float_fields = {
        "entry",
        "exit",
        "size",
        "notional",
        "commission",
        "slippage",
        "pnl",
        "pnl_return_pct",
        "entry_adx",
        "entry_rsi",
        "max_favorable",
        "max_adverse",
        "max_favorable_pct",
        "max_adverse_pct",
    }
    fields = [
        "symbol",
        "side",
        "entry_time",
        "exit_time",
        "entry",
        "exit",
        "size",
        "notional",
        "commission",
        "slippage",
        "pnl",
        "pnl_return_pct",
        "exit_reason",
        "entry_signal",
        "entry_regime",
        "entry_adx",
        "entry_rsi",
        "entry_orderbook_reason",
        "risk_reasons",
        "max_favorable",
        "max_adverse",
        "max_favorable_pct",
        "max_adverse_pct",
    ]
    return {
        field: _maybe_float(row.get(field)) if field in float_fields else _clean(row.get(field))
        for field in fields
        if field in row
    }


def trade_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [_maybe_float(row.get("pnl")) for row in rows]
    pnls = [pnl for pnl in pnls if pnl is not None]
    exits = Counter(_clean(row.get("exit_reason")) for row in rows)
    exits.pop(None, None)
    if not pnls:
        return {
            "count": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0,
            "best_pnl": 0.0,
            "worst_pnl": 0.0,
            "exit_reasons": dict(exits),
        }
    wins = sum(1 for pnl in pnls if pnl > 0)
    losses = sum(1 for pnl in pnls if pnl < 0)
    return {
        "count": len(pnls),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(wins / len(pnls) * 100.0, 4),
        "total_pnl": round(sum(pnls), 6),
        "avg_pnl": round(sum(pnls) / len(pnls), 6),
        "best_pnl": round(max(pnls), 6),
        "worst_pnl": round(min(pnls), 6),
        "exit_reasons": dict(exits),
    }


def latest_decisions_by_symbol(rows: list[dict[str, Any]], symbols: list[str]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = _clean(row.get("symbol"))
        if symbol:
            latest[str(symbol)] = row
    ordered = []
    for symbol in symbols:
        row = latest.get(symbol)
        if row:
            ordered.append(_compact_decision(row))
    return ordered


def build_report(decision_limit: int = 50) -> dict[str, Any]:
    symbols = list(getattr(config, "SYMBOLS", []))
    heartbeat = _read_json(getattr(config, "PAPER_HEARTBEAT_FILE", "paper_heartbeat.json"))
    decisions = _csv_tail(getattr(config, "PAPER_DECISIONS_CSV", "paper_decisions.csv"), decision_limit)
    equity_rows = _csv_tail(getattr(config, "PAPER_EQUITY_CSV", "paper_equity.csv"), 1)
    trade_rows = _csv_tail(getattr(config, "PAPER_TRADES_CSV", "paper_trades.csv"), decision_limit)
    error_rows = _csv_tail(getattr(config, "PAPER_ERRORS_CSV", "paper_errors.csv"), decision_limit)
    state = _read_json(getattr(config, "PAPER_STATE_FILE", "paper_state.json"))

    heartbeat_age = _utc_age_minutes(_clean(heartbeat.get("updated_at")))
    stale_limit = float(getattr(config, "OPS_HEARTBEAT_STALE_MINUTES", 180))
    symbol_set = set(symbols)
    active_decisions = [row for row in decisions if _clean(row.get("symbol")) in symbol_set]
    inactive_symbols = sorted({
        str(_clean(row.get("symbol"))) for row in decisions
        if _clean(row.get("symbol")) and _clean(row.get("symbol")) not in symbol_set
    })
    latest_decisions = latest_decisions_by_symbol(active_decisions, symbols)
    latest_symbols = {row.get("symbol") for row in latest_decisions if row.get("symbol")}
    actions = Counter(_clean(row.get("action")) for row in active_decisions)
    skips = Counter(_clean(row.get("skipped_reason")) for row in active_decisions)
    actions.pop(None, None)
    skips.pop(None, None)

    latest_equity = equity_rows[-1] if equity_rows else {}
    open_positions = [
        _compact_position(symbol, pos)
        for symbol, pos in sorted((state.get("positions") or {}).items())
        if isinstance(pos, dict)
    ]
    warnings: list[str] = []
    if not heartbeat:
        warnings.append("paper heartbeat missing")
    elif heartbeat_age is not None and heartbeat_age > stale_limit:
        warnings.append(f"paper heartbeat stale: {heartbeat_age:.1f} minutes")
    if not bool(getattr(config, "TESTNET", True)):
        warnings.append("TESTNET is false")
    if bool(getattr(config, "LIVE_TRADING_APPROVED", False)):
        warnings.append("LIVE_TRADING_APPROVED is true")
    missing_symbols = [symbol for symbol in symbols if symbol not in latest_symbols]
    if missing_symbols:
        warnings.append("missing recent decisions for: " + ",".join(missing_symbols))
    if error_rows:
        warnings.append(f"recent paper errors: {len(error_rows)}")

    return {
        "symbols": symbols,
        "runtime": {
            "run_tag": heartbeat.get("run_tag", getattr(config, "PAPER_RUN_TAG", "default")),
            "timeframe": heartbeat.get("timeframe", getattr(config, "TIMEFRAME", "")),
            "flow_period": heartbeat.get("flow_period", getattr(config, "FLOW_PERIOD", "")),
            "scaled_lookbacks": heartbeat.get(
                "scaled_lookbacks",
                bool(getattr(config, "PAPER_SCALED_LOOKBACKS", False)),
            ),
        },
        "safety": {
            "testnet": bool(getattr(config, "TESTNET", True)),
            "live_trading_approved": bool(getattr(config, "LIVE_TRADING_APPROVED", False)),
        },
        "heartbeat": {
            "status": heartbeat.get("status", "missing"),
            "pid": heartbeat.get("pid"),
            "age_minutes": round(heartbeat_age, 2) if heartbeat_age is not None else None,
            "wallet": heartbeat.get("wallet", _maybe_float(latest_equity.get("wallet"))),
            "equity": heartbeat.get("equity", _maybe_float(latest_equity.get("equity"))),
            "open_positions": heartbeat.get("open_positions", _maybe_float(latest_equity.get("open_positions"))),
            "decisions": heartbeat.get("decisions"),
            "closed_trades": heartbeat.get("closed_trades"),
        },
        "recent": {
            "decision_rows": len(active_decisions),
            "inactive_recent_symbols": inactive_symbols,
            "actions": dict(actions),
            "skips": dict(skips),
            "closed_trades": len(trade_rows),
            "trade_summary": trade_summary(trade_rows),
            "latest_trades": [_compact_trade(row) for row in trade_rows[-10:]],
            "errors": len(error_rows),
            "last_error": error_rows[-1] if error_rows else None,
            "last_trade": trade_rows[-1] if trade_rows else None,
        },
        "open_positions": open_positions,
        "latest_decisions": latest_decisions,
        "warnings": warnings,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def print_text(report: dict[str, Any]) -> None:
    heartbeat = report["heartbeat"]
    safety = report["safety"]
    recent = report["recent"]
    runtime = report["runtime"]

    print("=== PAPER REPORT ===")
    print("symbols:", ", ".join(report["symbols"]))
    print(
        "runtime:",
        f"tag={runtime['run_tag']}",
        f"timeframe={runtime['timeframe']}",
        f"flow={runtime['flow_period']}",
        f"scaled={runtime['scaled_lookbacks']}",
    )
    print(
        "heartbeat:",
        f"status={heartbeat['status']}",
        f"pid={heartbeat['pid']}",
        f"age_min={_fmt(heartbeat['age_minutes'])}",
        f"equity={_fmt(heartbeat['equity'])}",
        f"wallet={_fmt(heartbeat['wallet'])}",
        f"open={_fmt(heartbeat['open_positions'])}",
    )
    print(
        "safety:",
        f"TESTNET={safety['testnet']}",
        f"LIVE_TRADING_APPROVED={safety['live_trading_approved']}",
    )
    print("recent actions:", recent["actions"] or {})
    print("recent skips:", recent["skips"] or {})
    if recent["inactive_recent_symbols"]:
        print("inactive recent symbols:", ", ".join(recent["inactive_recent_symbols"]))
    summary = recent["trade_summary"]
    print(
        "trade summary:",
        f"count={summary['count']}",
        f"win_rate={summary['win_rate_pct']}%",
        f"total_pnl={summary['total_pnl']}",
        f"best={summary['best_pnl']}",
        f"worst={summary['worst_pnl']}",
    )
    print(f"recent closed trades: {recent['closed_trades']}  recent errors: {recent['errors']}")

    if report["open_positions"]:
        print("\nOpen positions:")
        header = f"{'symbol':<10} {'side':<5} {'entry_time':<19} {'entry':>10} {'size':>12} {'sl':>10} {'risk%':>7} {'MFE%':>7} {'MAE%':>7}"
        print(header)
        print("-" * len(header))
        for pos in report["open_positions"]:
            print(
                f"{_fmt(pos.get('symbol')):<10} {_fmt(pos.get('side')):<5} "
                f"{_fmt(pos.get('entry_time')):<19} {_fmt(pos.get('entry')):>10} "
                f"{_fmt(pos.get('size')):>12} {_fmt(pos.get('sl')):>10} "
                f"{_fmt((pos.get('risk_pct') or 0) * 100 if pos.get('risk_pct') is not None else None):>7} "
                f"{_fmt(pos.get('max_favorable_pct')):>7} {_fmt(pos.get('max_adverse_pct')):>7}"
            )

    if recent["latest_trades"]:
        print("\nLatest trades:")
        header = f"{'symbol':<10} {'side':<5} {'exit_time':<19} {'pnl':>10} {'ret%':>8} {'reason':<14} {'MFE%':>7} {'MAE%':>7}"
        print(header)
        print("-" * len(header))
        for trade in recent["latest_trades"][-5:]:
            print(
                f"{_fmt(trade.get('symbol')):<10} {_fmt(trade.get('side')):<5} "
                f"{_fmt(trade.get('exit_time')):<19} {_fmt(trade.get('pnl')):>10} "
                f"{_fmt(trade.get('pnl_return_pct')):>8} {_fmt(trade.get('exit_reason')):<14} "
                f"{_fmt(trade.get('max_favorable_pct')):>7} {_fmt(trade.get('max_adverse_pct')):>7}"
            )

    print("\nLatest decisions:")
    header = (
        f"{'symbol':<10} {'action':<11} {'bar_time':<19} {'close':>10} {'regime':<8} "
        f"{'adx':>6} {'rsi':>6} {'risk':>6} {'flow':>5} {'reason'}"
    )
    print(header)
    print("-" * len(header))
    for row in report["latest_decisions"]:
        reason = row.get("risk_reasons") or row.get("orderbook_reason") or row.get("signal") or ""
        print(
            f"{_fmt(row.get('symbol')):<10} {_fmt(row.get('action')):<11} "
            f"{_fmt(row.get('bar_time')):<19} {_fmt(row.get('close')):>10} "
            f"{_fmt(row.get('regime')):<8} {_fmt(row.get('adx')):>6} "
            f"{_fmt(row.get('rsi')):>6} {_fmt(row.get('risk_mult')):>6} "
            f"{_fmt(row.get('flow_fresh')):>5} {reason}"
        )

    if report["warnings"]:
        print("\nWarnings:")
        for warning in report["warnings"]:
            print("-", warning)
    else:
        print("\nWarnings: none")


def main() -> int:
    parser = argparse.ArgumentParser(description="Print detailed local paper telemetry report.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--tail", type=int, default=50, help="Number of recent rows to inspect.")
    parser.add_argument("--tag", default="", help="Read isolated paper files for this run tag.")
    args = parser.parse_args()

    with paper_runtime.temporary_paper_runtime(tag=args.tag):
        report = build_report(decision_limit=args.tail)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text(report)
    return 1 if report["warnings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
