from __future__ import annotations

from typing import Any

import config


def position_mode_status(exchange: Any) -> dict[str, Any]:
    if not getattr(config, "REQUIRE_ONE_WAY_MODE", True):
        return {
            "ok": True,
            "required": "any",
            "mode": "not_required",
            "dual_side_position": None,
            "reason": "",
        }

    try:
        response = exchange.fapiPrivateGetPositionSideDual()
    except Exception as exc:
        return {
            "ok": False,
            "required": "one_way",
            "mode": "unknown",
            "dual_side_position": None,
            "reason": f"position_mode_unavailable:{exc}",
        }

    dual = _boolish(response.get("dualSidePosition"))
    if dual is None:
        return {
            "ok": False,
            "required": "one_way",
            "mode": "unknown",
            "dual_side_position": response.get("dualSidePosition"),
            "reason": "position_mode_missing",
        }
    mode = "hedge" if dual else "one_way"
    return {
        "ok": not dual,
        "required": "one_way",
        "mode": mode,
        "dual_side_position": dual,
        "reason": "" if not dual else "hedge_mode_enabled",
    }


def leverage_status(exchange: Any, symbols: list[str] | None = None) -> dict[str, Any]:
    symbols = symbols or list(getattr(config, "SYMBOLS", [getattr(config, "SYMBOL", "")]))
    desired = int(getattr(config, "LEVERAGE", 1))
    try:
        positions = exchange.fetch_positions(symbols)
    except Exception as exc:
        return {
            "ok": False,
            "desired": desired,
            "symbols": [],
            "reason": f"leverage_unavailable:{exc}",
        }

    rows = []
    for symbol in symbols:
        pos = _find_position(positions, symbol)
        leverage = _extract_leverage(pos)
        ok = leverage == desired if leverage is not None else False
        rows.append({
            "symbol": symbol,
            "leverage": leverage,
            "ok": ok,
            "reason": "" if ok else ("leverage_missing" if leverage is None else f"leverage_mismatch:{leverage}!={desired}"),
        })

    bad = [row for row in rows if not row["ok"]]
    return {
        "ok": not bad,
        "desired": desired,
        "symbols": rows,
        "reason": "" if not bad else "symbol_leverage_not_confirmed",
    }


def margin_mode_status(exchange: Any, symbols: list[str] | None = None) -> dict[str, Any]:
    symbols = symbols or list(getattr(config, "SYMBOLS", [getattr(config, "SYMBOL", "")]))
    desired = str(getattr(config, "MARGIN_MODE", "cross")).lower()
    try:
        positions = exchange.fetch_positions(symbols)
    except Exception as exc:
        return {
            "ok": False,
            "desired": desired,
            "symbols": [],
            "reason": f"margin_mode_unavailable:{exc}",
        }

    rows = []
    for symbol in symbols:
        pos = _find_position(positions, symbol)
        mode = _extract_margin_mode(pos)
        ok = mode == desired if mode is not None else False
        rows.append({
            "symbol": symbol,
            "margin_mode": mode,
            "ok": ok,
            "reason": "" if ok else ("margin_mode_missing" if mode is None else f"margin_mode_mismatch:{mode}!={desired}"),
        })

    bad = [row for row in rows if not row["ok"]]
    return {
        "ok": not bad,
        "desired": desired,
        "symbols": rows,
        "reason": "" if not bad else "symbol_margin_mode_not_confirmed",
    }


def hard_stop_status(exchange: Any, symbols: list[str] | None = None) -> dict[str, Any]:
    symbols = symbols or list(getattr(config, "SYMBOLS", [getattr(config, "SYMBOL", "")]))
    try:
        positions = exchange.fetch_positions(symbols)
    except Exception as exc:
        return {
            "ok": False,
            "symbols": [],
            "reason": f"positions_unavailable:{exc}",
        }

    rows = []
    for symbol in symbols:
        pos = _find_position(positions, symbol)
        contracts = _contracts(pos)
        if contracts == 0:
            continue
        try:
            orders = exchange.fetch_open_orders(symbol)
        except Exception as exc:
            rows.append({
                "symbol": symbol,
                "contracts": contracts,
                "has_reduce_only_stop": False,
                "stop_order_id": None,
                "reason": f"open_orders_unavailable:{exc}",
                "ok": False,
            })
            continue

        stop = _find_reduce_only_stop(orders)
        rows.append({
            "symbol": symbol,
            "contracts": contracts,
            "has_reduce_only_stop": stop is not None,
            "stop_order_id": stop.get("id") if stop else None,
            "reason": "" if stop else "missing_reduce_only_stop",
            "ok": stop is not None,
        })

    bad = [row for row in rows if not row["ok"]]
    return {
        "ok": not bad,
        "symbols": rows,
        "reason": "" if not bad else "open_position_without_hard_stop",
    }


def account_safety_status(exchange: Any, symbols: list[str] | None = None) -> dict[str, Any]:
    mode = position_mode_status(exchange)
    leverage = leverage_status(exchange, symbols)
    margin = margin_mode_status(exchange, symbols)
    hard_stop = hard_stop_status(exchange, symbols)
    return {
        "ok": bool(mode["ok"] and leverage["ok"] and margin["ok"] and hard_stop["ok"]),
        "position_mode": mode,
        "leverage": leverage,
        "margin_mode": margin,
        "hard_stop": hard_stop,
    }


def confirm_set_leverage_response(response: Any, desired: int) -> bool:
    leverage = _extract_leverage(response)
    return True if leverage is None else leverage == int(desired)


def confirm_set_margin_mode_response(response: Any, desired: str) -> bool:
    mode = _extract_margin_mode(response)
    return True if mode is None else mode == str(desired).lower()


def _find_position(positions: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    target = _normalize_symbol(symbol)
    for pos in positions:
        candidates = [
            pos.get("symbol"),
            (pos.get("info") or {}).get("symbol"),
        ]
        if any(_normalize_symbol(str(candidate or "")) == target for candidate in candidates):
            return pos
    return None


def _extract_leverage(value: Any) -> int | None:
    if not value:
        return None
    if isinstance(value, dict):
        for key in ("leverage", "initialLeverage"):
            out = _intish(value.get(key))
            if out is not None:
                return out
        info = value.get("info") or {}
        for key in ("leverage", "initialLeverage"):
            out = _intish(info.get(key))
            if out is not None:
                return out
    return None


def _extract_margin_mode(value: Any) -> str | None:
    if not value or not isinstance(value, dict):
        return None
    for key in ("marginMode", "marginType"):
        out = _modeish(value.get(key))
        if out:
            return out
    isolated = _boolish(value.get("isolated"))
    if isolated is not None:
        return "isolated" if isolated else "cross"
    info = value.get("info") or {}
    for key in ("marginMode", "marginType"):
        out = _modeish(info.get(key))
        if out:
            return out
    isolated = _boolish(info.get("isolated"))
    if isolated is not None:
        return "isolated" if isolated else "cross"
    return None


def _find_reduce_only_stop(orders: list[dict[str, Any]]) -> dict[str, Any] | None:
    for order in orders:
        info = order.get("info") or {}
        order_type = str(order.get("type") or info.get("type") or info.get("origType") or "").lower()
        reduce_only = _boolish(order.get("reduceOnly", info.get("reduceOnly")))
        if reduce_only and "stop" in order_type:
            return order
    return None


def _contracts(pos: dict[str, Any] | None) -> float:
    if not pos:
        return 0.0
    try:
        return abs(float(pos.get("contracts") or pos.get("positionAmt") or (pos.get("info") or {}).get("positionAmt") or 0))
    except (TypeError, ValueError):
        return 0.0


def _normalize_symbol(symbol: str) -> str:
    return symbol.replace("/", "").split(":")[0].upper()


def _modeish(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"cross", "crossed"}:
        return "cross"
    if text == "isolated":
        return "isolated"
    return None


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _intish(value: Any) -> int | None:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None
