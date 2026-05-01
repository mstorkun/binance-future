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


def account_safety_status(exchange: Any, symbols: list[str] | None = None) -> dict[str, Any]:
    mode = position_mode_status(exchange)
    leverage = leverage_status(exchange, symbols)
    return {
        "ok": bool(mode["ok"] and leverage["ok"]),
        "position_mode": mode,
        "leverage": leverage,
    }


def confirm_set_leverage_response(response: Any, desired: int) -> bool:
    leverage = _extract_leverage(response)
    return True if leverage is None else leverage == int(desired)


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


def _normalize_symbol(symbol: str) -> str:
    return symbol.replace("/", "").split(":")[0].upper()


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
