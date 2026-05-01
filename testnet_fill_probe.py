"""
Tiny Binance Futures testnet fill probe.

This script can place and immediately close a small TESTNET market order to
measure real fill/slippage behavior. It is locked behind an explicit CLI flag
and refuses to run unless config.TESTNET is True.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import ccxt
import pandas as pd

import config
import data
import order_manager


def _utc_now() -> str:
    return pd.Timestamp.now(tz="UTC").isoformat()


def _append(row: dict, path: str = "testnet_fill_probe.csv") -> None:
    path = Path(path)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


class SimulatedPartialExchange:
    def __init__(self):
        self.cancelled = []
        self.created_orders = []
        self.orders = {}

    def cancel_order(self, order_id, symbol, params=None):
        self.cancelled.append({"order_id": order_id, "symbol": symbol, "params": params or {}})

    def fetch_order(self, order_id, symbol, params=None):
        return self.orders[order_id]

    def create_order(self, symbol, type, side, amount, params=None):
        order = {
            "id": f"sim-close-{len(self.created_orders) + 1}",
            "symbol": symbol,
            "type": type,
            "side": side,
            "amount": amount,
            "filled": amount,
            "average": 100.0,
            "clientOrderId": (params or {}).get("newClientOrderId"),
            "params": params or {},
        }
        self.created_orders.append(order)
        return order


class SimulatedDuplicateExchange:
    def __init__(self):
        self.created_params = []
        self.fetch_params = None

    def create_order(self, symbol, type, side, amount, params=None):
        self.created_params.append(params or {})
        raise ccxt.ExchangeError("-2010 Duplicate order sent")

    def fetch_order(self, order_id, symbol, params=None):
        self.fetch_params = params or {}
        return {
            "id": "sim-existing-order",
            "clientOrderId": self.fetch_params.get("origClientOrderId"),
            "amount": 1.0,
            "filled": 1.0,
            "average": 100.0,
        }


def run_simulation_probe(out: str) -> None:
    old_policy = getattr(config, "PARTIAL_FILL_POLICY", "abort")
    old_symbol = config.SYMBOL
    old_order_events_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
    rows = []
    try:
        config.SYMBOL = "DOGE/USDT"
        config.ORDER_EVENTS_JSONL = str(Path(out).with_suffix(".jsonl"))

        config.PARTIAL_FILL_POLICY = "abort"
        partial_exchange = SimulatedPartialExchange()
        partial_order = {
            "id": "sim-partial-entry",
            "clientOrderId": "sim-entry-cid",
            "amount": 20.0,
            "filled": 12.0,
            "remaining": 8.0,
            "average": 0.50,
        }
        partial_exchange.orders[partial_order["id"]] = partial_order
        fill = order_manager._resolve_market_fill(
            partial_exchange,
            partial_order,
            fallback_price=0.50,
            fallback_size=20.0,
            context="entry",
            position_side="long",
        )
        rows.append({
            "run_at_utc": _utc_now(),
            "probe": "partial_fill_simulation",
            "policy": "abort",
            "client_order_id": fill.client_order_id,
            "requested_qty": fill.requested_size,
            "filled_qty": fill.filled_size,
            "remaining_qty": fill.remaining_size,
            "partial": fill.partial,
            "aborted": fill.aborted,
            "cancelled_order_id": partial_exchange.cancelled[0]["order_id"] if partial_exchange.cancelled else "",
            "rollback_qty": partial_exchange.created_orders[0]["amount"] if partial_exchange.created_orders else 0.0,
            "duplicate_reconciled": "",
        })

        cid = order_manager.client_order_id(
            "DOGE/USDT",
            "entry",
            epoch_ms=1770000000000,
            nonce8="dupsim01",
        )
        duplicate_exchange = SimulatedDuplicateExchange()
        fetched, resolved_cid, duplicate = order_manager._create_order_idempotent(
            duplicate_exchange,
            symbol="DOGE/USDT",
            type="market",
            side="buy",
            amount=1.0,
            intent="entry",
            client_order_id_value=cid,
        )
        rows.append({
            "run_at_utc": _utc_now(),
            "probe": "duplicate_client_order_id_simulation",
            "policy": "",
            "client_order_id": resolved_cid,
            "requested_qty": 1.0,
            "filled_qty": fetched.get("filled"),
            "remaining_qty": 0.0,
            "partial": False,
            "aborted": False,
            "cancelled_order_id": "",
            "rollback_qty": 0.0,
            "duplicate_reconciled": duplicate and fetched.get("id") == "sim-existing-order",
        })
    finally:
        config.PARTIAL_FILL_POLICY = old_policy
        config.SYMBOL = old_symbol
        config.ORDER_EVENTS_JSONL = old_order_events_path

    for row in rows:
        _append(row, out)
    print("testnet fill probe simulation:", rows)


def _avg_price(order: dict, fallback: float) -> float:
    info = order.get("info") or {}
    for key in ("average", "avgPrice", "price"):
        value = order.get(key) or info.get(key)
        try:
            out = float(value)
        except (TypeError, ValueError):
            continue
        if out > 0:
            return out
    filled = order.get("filled") or info.get("executedQty")
    cost = order.get("cost") or info.get("cumQuote")
    try:
        filled = float(filled)
        cost = float(cost)
    except (TypeError, ValueError):
        return fallback
    return cost / filled if filled > 0 and cost > 0 else fallback


def _filled(order: dict, fallback: float) -> float:
    info = order.get("info") or {}
    for key in ("filled", "executedQty", "origQty"):
        value = order.get(key) or info.get(key)
        try:
            out = float(value)
        except (TypeError, ValueError):
            continue
        if out > 0:
            return out
    return fallback


def _safe_reduce_only_close(exchange, symbol: str, side: str, amount: float) -> dict | None:
    close_side = "sell" if side == "long" else "buy"
    try:
        order, _, _ = order_manager._create_order_idempotent(
            exchange,
            symbol=symbol,
            type="market",
            side=close_side,
            amount=amount,
            intent="emergency_close",
            params={"reduceOnly": True, "newOrderRespType": "RESULT"},
        )
        return order
    except Exception as exc:
        print(f"EMERGENCY TESTNET CLOSE FAILED: {exc}")
        return None


def run_probe(symbol: str, side: str, notional: float, approve: bool) -> None:
    if not approve:
        raise SystemExit("Refusing to send testnet order without --approve-testnet-fill.")
    if not config.TESTNET:
        raise SystemExit("Refusing to run fill probe unless config.TESTNET is True.")
    if not config.API_KEY or not config.API_SECRET:
        raise SystemExit("Missing BINANCE_API_KEY / BINANCE_API_SECRET.")

    exchange = data.make_exchange()
    ticker = exchange.fetch_ticker(symbol)
    ref_price = float(ticker["last"] or ticker["close"])
    amount = float(exchange.amount_to_precision(symbol, notional / ref_price))
    order_side = "buy" if side == "long" else "sell"
    close_side = "sell" if side == "long" else "buy"

    entry_order = None
    close_order = None
    filled = 0.0
    try:
        entry_order, entry_client_order_id, entry_duplicate = order_manager._create_order_idempotent(
            exchange,
            symbol=symbol,
            type="market",
            side=order_side,
            amount=amount,
            intent="entry",
            params={"newOrderRespType": "RESULT"},
        )
        entry = _avg_price(entry_order, ref_price)
        filled = _filled(entry_order, amount)
        close_order, close_client_order_id, close_duplicate = order_manager._create_order_idempotent(
            exchange,
            symbol=symbol,
            type="market",
            side=close_side,
            amount=filled,
            intent="close",
            params={"reduceOnly": True, "newOrderRespType": "RESULT"},
        )
        exit_price = _avg_price(close_order, entry)
    except Exception:
        if filled > 0:
            close_order = _safe_reduce_only_close(exchange, symbol, side, filled)
        raise

    row = {
        "run_at_utc": _utc_now(),
        "symbol": symbol,
        "side": side,
        "requested_notional": notional,
        "amount": filled,
        "ref_price": ref_price,
        "entry_fill": entry,
        "exit_fill": exit_price,
        "entry_slippage_pct": ((entry - ref_price) / ref_price * 100.0) if side == "long" else ((ref_price - entry) / ref_price * 100.0),
        "round_trip_move_pct": ((exit_price - entry) / entry * 100.0) if side == "long" else ((entry - exit_price) / entry * 100.0),
        "entry_order_id": entry_order.get("id"),
        "close_order_id": close_order.get("id"),
        "entry_client_order_id": entry_client_order_id,
        "close_client_order_id": close_client_order_id,
        "entry_duplicate_reconciled": entry_duplicate,
        "close_duplicate_reconciled": close_duplicate,
    }
    _append(row)
    print("testnet fill probe:", row)


def run_duplicate_client_order_probe(symbol: str, side: str, notional: float, approve: bool) -> None:
    if not approve:
        raise SystemExit("Refusing to send testnet order without --approve-testnet-fill.")
    if not config.TESTNET:
        raise SystemExit("Refusing to run duplicate client order probe unless config.TESTNET is True.")
    if not config.API_KEY or not config.API_SECRET:
        raise SystemExit("Missing BINANCE_API_KEY / BINANCE_API_SECRET.")

    exchange = data.make_exchange()
    ticker = exchange.fetch_ticker(symbol)
    ref_price = float(ticker["last"] or ticker["close"])
    amount = float(exchange.amount_to_precision(symbol, notional / ref_price))
    order_side = "buy" if side == "long" else "sell"
    close_side = "sell" if side == "long" else "buy"
    cid = order_manager.client_order_id(symbol, "entry")

    first_order = None
    second_order = None
    close_order = None
    try:
        first_order, first_cid, first_duplicate = order_manager._create_order_idempotent(
            exchange,
            symbol=symbol,
            type="market",
            side=order_side,
            amount=amount,
            intent="entry",
            params={"newOrderRespType": "RESULT"},
            client_order_id_value=cid,
        )
        second_order, second_cid, second_duplicate = order_manager._create_order_idempotent(
            exchange,
            symbol=symbol,
            type="market",
            side=order_side,
            amount=amount,
            intent="entry",
            params={"newOrderRespType": "RESULT"},
            client_order_id_value=cid,
        )

        filled_by_order_id = {}
        for order in (first_order, second_order):
            oid = order.get("id") or (order.get("info") or {}).get("orderId") or id(order)
            filled_by_order_id[str(oid)] = _filled(order, amount)
        total_filled = sum(filled_by_order_id.values())
        if total_filled > 0:
            close_order, close_cid, close_duplicate = order_manager._create_order_idempotent(
                exchange,
                symbol=symbol,
                type="market",
                side=close_side,
                amount=total_filled,
                intent="close",
                params={"reduceOnly": True, "newOrderRespType": "RESULT"},
            )
        else:
            close_cid = ""
            close_duplicate = False
    except Exception:
        filled = 0.0
        for order in (first_order, second_order):
            if order:
                filled += _filled(order, 0.0)
        if filled > 0:
            close_order = _safe_reduce_only_close(exchange, symbol, side, filled)
        raise

    row = {
        "run_at_utc": _utc_now(),
        "symbol": symbol,
        "side": side,
        "requested_notional": notional,
        "amount": amount,
        "client_order_id": cid,
        "first_order_id": first_order.get("id") if first_order else "",
        "second_order_id": second_order.get("id") if second_order else "",
        "same_order_id": (first_order or {}).get("id") == (second_order or {}).get("id"),
        "first_duplicate_reconciled": first_duplicate,
        "second_duplicate_reconciled": second_duplicate,
        "first_client_order_id": first_cid,
        "second_client_order_id": second_cid,
        "close_order_id": close_order.get("id") if close_order else "",
        "close_client_order_id": close_cid,
        "close_duplicate_reconciled": close_duplicate,
    }
    _append(row, "testnet_duplicate_client_order_probe.csv")
    print("testnet duplicate client order probe:", row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default=config.SYMBOLS[0])
    parser.add_argument("--side", choices=("long", "short"), default="long")
    parser.add_argument("--notional", type=float, default=getattr(config, "TESTNET_FILL_PROBE_NOTIONAL_USDT", 110.0))
    parser.add_argument("--approve-testnet-fill", action="store_true")
    parser.add_argument("--simulate-partial-fill", action="store_true")
    parser.add_argument("--simulate-duplicate-client-order-id", action="store_true")
    parser.add_argument("--probe-duplicate-client-order-id-real", action="store_true")
    parser.add_argument("--simulation-out", default="testnet_fill_probe_simulation.csv")
    args = parser.parse_args()
    if args.probe_duplicate_client_order_id_real:
        run_duplicate_client_order_probe(args.symbol, args.side, args.notional, args.approve_testnet_fill)
        return
    if args.simulate_partial_fill or args.simulate_duplicate_client_order_id:
        run_simulation_probe(args.simulation_out)
        return
    run_probe(args.symbol, args.side, args.notional, args.approve_testnet_fill)


if __name__ == "__main__":
    main()
