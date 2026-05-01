from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd

import config

log = logging.getLogger(__name__)


def utc_now() -> str:
    return pd.Timestamp.now(tz="UTC").isoformat()


def load_state(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path or getattr(config, "LIVE_STATE_FILE", "live_state.json"))
    if not target.exists():
        return _empty_state()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        log.error(f"Live state okunamadi, bos state kullaniliyor: {exc}")
        return _empty_state()
    data.setdefault("positions", {})
    data.setdefault("created_at", utc_now())
    return data


def save_state(state: dict[str, Any], path: str | Path | None = None) -> None:
    target = Path(path or getattr(config, "LIVE_STATE_FILE", "live_state.json"))
    state["updated_at"] = utc_now()
    state["symbols"] = list(getattr(config, "SYMBOLS", []))
    state["testnet"] = bool(getattr(config, "TESTNET", True))
    if target.parent and str(target.parent) != ".":
        target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(_clean(state), indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, target)


def load_positions(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    return dict(load_state(path).get("positions") or {})


def save_positions(positions: dict[str, dict[str, Any]], path: str | Path | None = None) -> None:
    state = load_state(path)
    state["positions"] = positions
    save_state(state, path)


def upsert_position(symbol: str, position: dict[str, Any], path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    positions = load_positions(path)
    positions[symbol] = _clean_position(position)
    save_positions(positions, path)
    return positions


def remove_position(symbol: str, path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    positions = load_positions(path)
    positions.pop(symbol, None)
    save_positions(positions, path)
    return positions


def clear_positions(path: str | Path | None = None) -> None:
    save_positions({}, path)


def reconcile_positions(
    local_positions: dict[str, dict[str, Any]],
    exchange_positions: list[dict[str, Any]],
    symbols: list[str],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Drop local positions that are no longer open on the exchange.

    This is intentionally conservative: it does not invent new local state for
    newly discovered exchange positions because ATR/SL recovery needs symbol
    data. `bot._recover_position` handles that per symbol.
    """
    open_symbols = {_normalize_symbol(_position_symbol(pos)) for pos in exchange_positions if _contracts(pos) != 0}
    desired = {_normalize_symbol(sym) for sym in symbols}
    reconciled = {
        sym: pos
        for sym, pos in local_positions.items()
        if _normalize_symbol(sym) in open_symbols and _normalize_symbol(sym) in desired
    }
    removed = sorted(set(local_positions) - set(reconciled))
    return reconciled, removed


def _empty_state() -> dict[str, Any]:
    return {
        "created_at": utc_now(),
        "positions": {},
        "symbols": list(getattr(config, "SYMBOLS", [])),
        "testnet": bool(getattr(config, "TESTNET", True)),
    }


def _clean_position(position: dict[str, Any]) -> dict[str, Any]:
    return {str(k): _clean(v) for k, v in position.items()}


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def _position_symbol(pos: dict[str, Any]) -> str:
    return str(pos.get("symbol") or (pos.get("info") or {}).get("symbol") or "")


def _normalize_symbol(symbol: str) -> str:
    return symbol.replace("/", "").split(":")[0].upper()


def _contracts(pos: dict[str, Any]) -> float:
    try:
        return float(pos.get("contracts") or pos.get("positionAmt") or (pos.get("info") or {}).get("positionAmt") or 0)
    except (TypeError, ValueError):
        return 0.0
