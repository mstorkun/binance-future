from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import ccxt
import pandas as pd

import config
import data
import exchange_filters as xf
import order_events
import order_manager

log = logging.getLogger(__name__)


def run_kill_switch(
    exchange: Any,
    symbols: list[str],
    *,
    execute: bool = False,
    cancel_orders: bool = True,
    close_positions: bool = True,
) -> dict[str, Any]:
    """Build and optionally execute an emergency cancel/close plan.

    Default dry-run mode performs read-only exchange queries. Execution is
    intentionally explicit so this script can be used safely for status checks.
    """
    symbols = _dedupe_symbols(symbols)
    report = build_plan(
        exchange,
        symbols,
        cancel_orders=cancel_orders,
        close_positions=close_positions,
    )
    report["execute"] = bool(execute)
    if not execute:
        return report

    for row in report["symbols"]:
        symbol = row["symbol"]
        if cancel_orders:
            for order in row.get("open_orders", []):
                _execute_cancel(exchange, symbol, order, report)
        if close_positions:
            for position in row.get("positions", []):
                _execute_close(exchange, symbol, position, report)
    return report


def build_plan(
    exchange: Any,
    symbols: list[str],
    *,
    cancel_orders: bool = True,
    close_positions: bool = True,
) -> dict[str, Any]:
    symbols = _dedupe_symbols(symbols)
    positions = _fetch_positions(exchange, symbols) if close_positions else []
    rows = []
    for symbol in symbols:
        open_orders = _fetch_open_orders(exchange, symbol) if cancel_orders else []
        symbol_positions = [
            _position_summary(pos, symbol)
            for pos in positions
            if _same_symbol(_position_symbol(pos, symbol), symbol) and _position_summary(pos, symbol)
        ]
        rows.append({
            "symbol": symbol,
            "open_order_count": len(open_orders),
            "open_orders": [_order_summary(order) for order in open_orders],
            "position_count": len(symbol_positions),
            "positions": symbol_positions,
        })

    return {
        "ts": pd.Timestamp.now(tz="UTC").isoformat(),
        "execute": False,
        "testnet": bool(getattr(config, "TESTNET", True)),
        "live_trading_approved": bool(getattr(config, "LIVE_TRADING_APPROVED", False)),
        "cancel_orders": bool(cancel_orders),
        "close_positions": bool(close_positions),
        "symbols": rows,
        "totals": {
            "symbols": len(symbols),
            "open_orders": sum(row["open_order_count"] for row in rows),
            "positions": sum(row["position_count"] for row in rows),
            "cancelled": 0,
            "closed": 0,
            "errors": 0,
        },
        "errors": [],
    }


def configured_symbols() -> list[str]:
    symbols = list(getattr(config, "SYMBOLS", []) or [])
    if not symbols:
        symbols = [getattr(config, "SYMBOL", "")]
    return _dedupe_symbols(symbols)


def _execute_cancel(exchange: Any, symbol: str, order: dict[str, Any], report: dict[str, Any]) -> None:
    order_id = order.get("id")
    if not order_id:
        _record_error(report, "cancel_missing_order_id", symbol=symbol, order=order)
        return
    try:
        _cancel_order(exchange, str(order_id), symbol)
        report["totals"]["cancelled"] += 1
        order_events.record("kill_switch_cancel_ack", symbol=symbol, order_id=order_id)
    except Exception as exc:
        _record_error(report, "cancel_failed", symbol=symbol, order_id=order_id, error=str(exc))
        order_events.record("kill_switch_cancel_error", symbol=symbol, order_id=order_id, error=str(exc))


def _execute_close(exchange: Any, symbol: str, position: dict[str, Any], report: dict[str, Any]) -> None:
    amount = _float(position.get("amount"))
    close_side = str(position.get("close_side") or "")
    if amount is None or amount <= 0 or close_side not in {"buy", "sell"}:
        _record_error(report, "close_bad_position", symbol=symbol, position=position)
        return

    normalized = xf.normalize_market_amount(exchange, symbol, amount)
    if not normalized.ok or normalized.amount is None:
        _record_error(report, "close_amount_rejected", symbol=symbol, amount=amount, reason=normalized.reason)
        order_events.record(
            "kill_switch_close_amount_rejected",
            symbol=symbol,
            amount=amount,
            reason=normalized.reason,
        )
        return

    cid = order_manager.client_order_id(symbol, "emergency_close")
    order_events.record(
        "kill_switch_close_submit",
        symbol=symbol,
        side=close_side,
        amount=normalized.amount,
        requested_amount=amount,
        reduce_only=True,
        client_order_id=cid,
    )
    try:
        order, resolved_cid, duplicate = order_manager._create_order_idempotent(
            exchange,
            symbol=symbol,
            type="market",
            side=close_side,
            amount=normalized.amount,
            intent="emergency_close",
            params={"reduceOnly": True},
            client_order_id_value=cid,
        )
        report["totals"]["closed"] += 1
        order_events.record(
            "kill_switch_close_ack",
            symbol=symbol,
            client_order_id=resolved_cid,
            duplicate=duplicate,
            order=order_events.extract_order_summary(order),
        )
    except Exception as exc:
        _record_error(report, "close_failed", symbol=symbol, side=close_side, amount=normalized.amount, error=str(exc))
        order_events.record(
            "kill_switch_close_error",
            symbol=symbol,
            client_order_id=cid,
            side=close_side,
            amount=normalized.amount,
            error=str(exc),
        )


def _make_exchange_for_cli(allow_live: bool) -> ccxt.Exchange:
    if bool(getattr(config, "TESTNET", True)):
        return data.make_exchange()
    if not allow_live:
        raise RuntimeError("Live emergency kill switch requires --allow-live.")
    params = {
        "apiKey": config.API_KEY,
        "secret": config.API_SECRET,
        "options": {
            "defaultType": "future",
            "adjustForTimeDifference": bool(getattr(config, "ADJUST_FOR_TIME_DIFFERENCE", True)),
            "recvWindow": int(getattr(config, "RECV_WINDOW_MS", 5000)),
        },
    }
    return ccxt.binance(params)


def _fetch_open_orders(exchange: Any, symbol: str) -> list[dict[str, Any]]:
    try:
        return list(exchange.fetch_open_orders(symbol, params=order_manager.signed_params()) or [])
    except TypeError:
        return list(exchange.fetch_open_orders(symbol) or [])


def _fetch_positions(exchange: Any, symbols: list[str]) -> list[dict[str, Any]]:
    return list(exchange.fetch_positions(symbols) or [])


def _cancel_order(exchange: Any, order_id: str, symbol: str) -> None:
    try:
        exchange.cancel_order(order_id, symbol, order_manager.signed_params())
    except TypeError:
        exchange.cancel_order(order_id, symbol)


def _position_summary(pos: dict[str, Any], fallback_symbol: str) -> dict[str, Any] | None:
    amount, side = _position_amount_and_side(pos)
    if amount is None or amount <= 0 or side not in {"long", "short"}:
        return None
    return {
        "symbol": _position_symbol(pos, fallback_symbol),
        "side": side,
        "close_side": "sell" if side == "long" else "buy",
        "amount": amount,
        "entry_price": _float(pos.get("entryPrice") or (pos.get("info") or {}).get("entryPrice")),
        "unrealized_pnl": _float(pos.get("unrealizedPnl") or (pos.get("info") or {}).get("unRealizedProfit")),
    }


def _position_amount_and_side(pos: dict[str, Any]) -> tuple[float | None, str | None]:
    info = pos.get("info") or {}
    raw_position_amt = _float(pos.get("positionAmt") or info.get("positionAmt"))
    if raw_position_amt is not None and raw_position_amt != 0:
        return abs(raw_position_amt), "long" if raw_position_amt > 0 else "short"

    contracts = _float(pos.get("contracts"))
    if contracts is None or contracts == 0:
        return None, None
    side = str(pos.get("side") or info.get("positionSide") or "").lower()
    if side not in {"long", "short"}:
        return abs(contracts), "long" if contracts > 0 else "short"
    return abs(contracts), side


def _order_summary(order: dict[str, Any]) -> dict[str, Any]:
    info = order.get("info") or {}
    return {
        "id": order.get("id") or info.get("orderId"),
        "client_order_id": order.get("clientOrderId") or info.get("clientOrderId"),
        "type": order.get("type") or info.get("type") or info.get("origType"),
        "side": order.get("side") or info.get("side"),
        "amount": _float(order.get("amount") or info.get("origQty")),
        "price": _float(order.get("price") or info.get("price")),
        "stop_price": _float(order.get("stopPrice") or order.get("triggerPrice") or info.get("stopPrice")),
        "reduce_only": order.get("reduceOnly", info.get("reduceOnly")),
    }


def _record_error(report: dict[str, Any], code: str, **fields: Any) -> None:
    report["totals"]["errors"] += 1
    report["errors"].append({"code": code, **fields})


def _position_symbol(pos: dict[str, Any], fallback: str) -> str:
    return str(pos.get("symbol") or (pos.get("info") or {}).get("symbol") or fallback)


def _same_symbol(left: str, right: str) -> bool:
    return _normalize_symbol(left) == _normalize_symbol(right)


def _normalize_symbol(symbol: str) -> str:
    return str(symbol).replace("/", "").replace(":", "").upper()


def _dedupe_symbols(symbols: list[str]) -> list[str]:
    out = []
    seen = set()
    for symbol in symbols:
        symbol = str(symbol).strip()
        if not symbol:
            continue
        key = _normalize_symbol(symbol)
        if key not in seen:
            seen.add(key)
            out.append(symbol)
    return out


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Emergency cancel/close kill switch for Binance Futures.")
    parser.add_argument("--symbol", action="append", default=[], help="Symbol to include. Defaults to config.SYMBOLS.")
    parser.add_argument("--execute", action="store_true", help="Execute cancels/closes. Default is dry-run only.")
    parser.add_argument("--yes-i-understand", action="store_true", help="Required with --execute.")
    parser.add_argument("--allow-live", action="store_true", help="Allow running against live config.TESTNET=False.")
    parser.add_argument("--skip-cancel", action="store_true", help="Do not cancel open orders.")
    parser.add_argument("--skip-close", action="store_true", help="Do not close open positions.")
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    args = parser.parse_args()

    if args.execute and not args.yes_i_understand:
        print("--execute requires --yes-i-understand", flush=True)
        return 2

    try:
        exchange = _make_exchange_for_cli(args.allow_live)
        report = run_kill_switch(
            exchange,
            args.symbol or configured_symbols(),
            execute=args.execute,
            cancel_orders=not args.skip_cancel,
            close_positions=not args.skip_close,
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        else:
            print(f"Emergency kill switch failed: {exc}")
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("=== EMERGENCY KILL SWITCH ===")
        print(f"execute: {report['execute']}")
        print(f"testnet: {report['testnet']}")
        print(f"symbols: {report['totals']['symbols']}")
        print(f"open_orders: {report['totals']['open_orders']}")
        print(f"positions: {report['totals']['positions']}")
        print(f"cancelled: {report['totals']['cancelled']}")
        print(f"closed: {report['totals']['closed']}")
        print(f"errors: {report['totals']['errors']}")
    return 1 if report["totals"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
