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

import pandas as pd

import config
import data


def _utc_now() -> str:
    return pd.Timestamp.now(tz="UTC").isoformat()


def _append(row: dict) -> None:
    path = Path("testnet_fill_probe.csv")
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


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

    entry_order = exchange.create_order(symbol, "market", order_side, amount, params={"newOrderRespType": "RESULT"})
    entry = _avg_price(entry_order, ref_price)
    filled = _filled(entry_order, amount)
    close_order = exchange.create_order(symbol, "market", close_side, filled, params={"reduceOnly": True, "newOrderRespType": "RESULT"})
    exit_price = _avg_price(close_order, entry)

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
    }
    _append(row)
    print("testnet fill probe:", row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default=config.SYMBOLS[0])
    parser.add_argument("--side", choices=("long", "short"), default="long")
    parser.add_argument("--notional", type=float, default=getattr(config, "TESTNET_FILL_PROBE_NOTIONAL_USDT", 110.0))
    parser.add_argument("--approve-testnet-fill", action="store_true")
    args = parser.parse_args()
    run_probe(args.symbol, args.side, args.notional, args.approve_testnet_fill)


if __name__ == "__main__":
    main()
