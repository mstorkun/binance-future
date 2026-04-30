from __future__ import annotations

from dataclasses import dataclass
import math

import config


@dataclass(frozen=True)
class LiquidationDecision:
    ok: bool
    liquidation_price: float | None
    reason: str


def approximate_liquidation_price(
    entry: float,
    side: str,
    leverage: float | None = None,
    maintenance_margin_rate: float | None = None,
) -> float | None:
    """
    Approximate USD-M futures liquidation level for risk screening.

    Binance's full cross-margin formula also depends on wallet balance,
    maintenance amount tiers, other positions, unrealized PnL, and mark price.
    This approximation is a conservative guard, not an accounting replacement.
    """
    entry = _num(entry)
    leverage = _num(leverage if leverage is not None else config.LEVERAGE)
    mmr = _num(
        maintenance_margin_rate
        if maintenance_margin_rate is not None
        else getattr(config, "MAINTENANCE_MARGIN_RATE", 0.005)
    )
    if entry is None or leverage is None or mmr is None or entry <= 0 or leverage <= 0:
        return None

    if side == "long":
        return entry * (1.0 - (1.0 / leverage) + mmr)
    if side == "short":
        return entry * (1.0 + (1.0 / leverage) - mmr)
    return None


def liquidation_guard_decision(
    entry: float,
    side: str,
    hard_stop: float,
    leverage: float | None = None,
) -> LiquidationDecision:
    if not getattr(config, "LIQUIDATION_GUARD_ENABLED", True):
        return LiquidationDecision(True, None, "")

    liq = approximate_liquidation_price(entry, side, leverage=leverage)
    hard_stop = _num(hard_stop)
    if liq is None or hard_stop is None:
        return LiquidationDecision(False, liq, "liquidation_guard_bad_input")

    buffer_pct = float(getattr(config, "LIQUIDATION_BUFFER_PCT", 0.015))
    if side == "long":
        min_stop = liq * (1.0 + buffer_pct)
        if hard_stop <= min_stop:
            return LiquidationDecision(False, liq, f"hard_stop_too_close_to_liq:{hard_stop:.4f}<={min_stop:.4f}")
    elif side == "short":
        max_stop = liq * (1.0 - buffer_pct)
        if hard_stop >= max_stop:
            return LiquidationDecision(False, liq, f"hard_stop_too_close_to_liq:{hard_stop:.4f}>={max_stop:.4f}")
    else:
        return LiquidationDecision(False, liq, "liquidation_guard_bad_side")

    return LiquidationDecision(True, liq, "")


def _num(value, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default
