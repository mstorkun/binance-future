from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


DEFAULT_TARGET_ANNUAL_VOL = 0.60
DEFAULT_PER_POSITION_MAX_EQUITY = 0.20
DEFAULT_MAX_CONCURRENT = 4


@dataclass(frozen=True)
class VolTargetSize:
    notional: float
    margin_required: float
    target_vol: float
    realized_vol: float
    leverage_cap: float
    per_position_max_equity: float
    capped_by: str


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def position_notional(
    *,
    equity: float,
    realized_vol: float,
    target_vol: float = DEFAULT_TARGET_ANNUAL_VOL,
    leverage_cap: float = 10.0,
    per_position_max_pct: float = DEFAULT_PER_POSITION_MAX_EQUITY,
    min_realized_vol: float = 0.05,
) -> float:
    equity = max(_num(equity), 0.0)
    realized_vol = max(_num(realized_vol), float(min_realized_vol))
    target_vol = max(_num(target_vol), 0.0)
    leverage_cap = max(_num(leverage_cap), 0.0)
    per_position_max_pct = max(_num(per_position_max_pct), 0.0)
    raw_notional = equity * target_vol / realized_vol
    cap_notional = equity * leverage_cap * per_position_max_pct
    return round(float(min(raw_notional, cap_notional)), 8)


def sizing_decision(
    *,
    equity: float,
    realized_vol: float,
    target_vol: float = DEFAULT_TARGET_ANNUAL_VOL,
    leverage_cap: float = 10.0,
    per_position_max_pct: float = DEFAULT_PER_POSITION_MAX_EQUITY,
    min_realized_vol: float = 0.05,
) -> VolTargetSize:
    equity_value = max(_num(equity), 0.0)
    vol_value = max(_num(realized_vol), float(min_realized_vol))
    raw_notional = equity_value * max(_num(target_vol), 0.0) / vol_value
    cap_notional = equity_value * max(_num(leverage_cap), 0.0) * max(_num(per_position_max_pct), 0.0)
    notional = min(raw_notional, cap_notional)
    capped_by = "vol_target" if raw_notional <= cap_notional else "per_position_cap"
    leverage = max(_num(leverage_cap), 1e-9)
    return VolTargetSize(
        notional=round(float(notional), 8),
        margin_required=round(float(notional) / leverage, 8),
        target_vol=round(float(max(_num(target_vol), 0.0)), 8),
        realized_vol=round(float(vol_value), 8),
        leverage_cap=round(float(leverage), 8),
        per_position_max_equity=round(float(max(_num(per_position_max_pct), 0.0)), 8),
        capped_by=capped_by,
    )


def portfolio_notional_cap(
    *,
    equity: float,
    leverage_cap: float = 10.0,
    per_position_max_pct: float = DEFAULT_PER_POSITION_MAX_EQUITY,
    max_concurrent: int = DEFAULT_MAX_CONCURRENT,
) -> float:
    equity = max(_num(equity), 0.0)
    return round(float(equity * max(_num(leverage_cap), 0.0) * max(_num(per_position_max_pct), 0.0) * max(int(max_concurrent), 0)), 8)
