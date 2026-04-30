"""
Execution guards against one-bar wicks, thin books, and fragile stop triggers.

The key split is:
- soft stop: strategy stop managed by the bot with close confirmation
- hard stop: wider exchange-side fail-safe in case the bot/network is down
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import config


@dataclass(frozen=True)
class GuardDecision:
    ok: bool
    reason: str = ""


@dataclass(frozen=True)
class StopDecision:
    hit: bool
    reason: str = ""
    price: float | None = None


def hard_stop_from_soft(soft_sl: float, atr: float, side: str) -> float:
    extra = atr * getattr(config, "HARD_STOP_EXTRA_ATR", 1.0)
    if side == "long":
        return round(soft_sl - extra, 2)
    return round(soft_sl + extra, 2)


def exchange_stop_params(stop_price: float) -> dict:
    params: dict[str, Any] = {"stopPrice": stop_price, "reduceOnly": True}
    if getattr(config, "USE_MARK_PRICE_STOPS", True):
        params["workingType"] = "MARK_PRICE"
    if getattr(config, "USE_PRICE_PROTECT", True):
        params["priceProtect"] = "TRUE"
    return params


def is_spike_bar(bar) -> bool:
    if not getattr(config, "WICK_GUARD_ENABLED", True):
        return False

    atr = _num(_get(bar, "atr"))
    high = _num(_get(bar, "high"))
    low = _num(_get(bar, "low"))
    open_ = _num(_get(bar, "open"))
    close = _num(_get(bar, "close"))
    if not all(v is not None for v in (atr, high, low, open_, close)) or atr <= 0:
        return False

    bar_range = high - low
    body = max(abs(close - open_), max(close, 1e-9) * 0.0001)
    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low
    wick_body_ratio = max(upper_wick, lower_wick) / body
    range_atr = bar_range / atr

    volume = _num(_get(bar, "volume"))
    volume_ma = _num(_get(bar, "volume_ma"))
    volume_ok = True
    if volume is not None and volume_ma is not None and volume_ma > 0:
        volume_ok = volume >= volume_ma * getattr(config, "WICK_GUARD_VOLUME_MULT", 2.0)

    return (
        range_atr >= getattr(config, "WICK_GUARD_RANGE_ATR_MULT", 2.5)
        and wick_body_ratio >= getattr(config, "WICK_GUARD_WICK_BODY_RATIO", 2.5)
        and volume_ok
    )


def should_skip_trailing_update(bar) -> GuardDecision:
    if is_spike_bar(bar):
        return GuardDecision(False, "spike_bar_skip_trailing")
    return GuardDecision(True, "")


def stop_decision(position: dict, bar) -> StopDecision:
    side = position["side"]
    soft_sl = float(position["sl"])
    hard_sl = float(position.get("hard_sl", soft_sl))
    close = float(_get(bar, "close"))
    high = float(_get(bar, "high"))
    low = float(_get(bar, "low"))
    spike = is_spike_bar(bar)

    if side == "long":
        if spike and getattr(config, "SOFT_STOP_CLOSE_CONFIRM", True):
            if close <= hard_sl:
                return StopDecision(True, "hard_sl", hard_sl)
            if close <= soft_sl:
                return StopDecision(True, "soft_sl_confirmed", close)
            return StopDecision(False, "soft_sl_wick_ignored" if low <= soft_sl else "")
        if low <= soft_sl:
            return StopDecision(True, "soft_sl", soft_sl)
        if low <= hard_sl:
            return StopDecision(True, "hard_sl", hard_sl)
    else:
        if spike and getattr(config, "SOFT_STOP_CLOSE_CONFIRM", True):
            if close >= hard_sl:
                return StopDecision(True, "hard_sl", hard_sl)
            if close >= soft_sl:
                return StopDecision(True, "soft_sl_confirmed", close)
            return StopDecision(False, "soft_sl_wick_ignored" if high >= soft_sl else "")
        if high >= soft_sl:
            return StopDecision(True, "soft_sl", soft_sl)
        if high >= hard_sl:
            return StopDecision(True, "hard_sl", hard_sl)

    return StopDecision(False, "")


def pre_trade_liquidity_check(exchange, symbol: str, side: str, notional: float, ref_price: float) -> GuardDecision:
    if not getattr(config, "ORDER_BOOK_GUARD_ENABLED", True):
        return GuardDecision(True, "")

    try:
        book = exchange.fetch_order_book(symbol, limit=20)
    except Exception as exc:
        if getattr(config, "ORDER_BOOK_GUARD_FAIL_CLOSED", True):
            return GuardDecision(False, f"orderbook_unavailable:{exc}")
        return GuardDecision(True, "orderbook_unavailable_fail_open")

    bids = book.get("bids") or []
    asks = book.get("asks") or []
    if not bids or not asks:
        return GuardDecision(False, "orderbook_empty")

    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    mid = (best_bid + best_ask) / 2
    if mid <= 0:
        return GuardDecision(False, "orderbook_bad_mid")

    spread_pct = (best_ask - best_bid) / mid
    if spread_pct > getattr(config, "MAX_SPREAD_PCT", 0.0015):
        return GuardDecision(False, f"spread_too_wide:{spread_pct:.5f}")

    band_pct = getattr(config, "ORDER_BOOK_DEPTH_BAND_PCT", 0.002)
    levels = asks if side == "long" else bids
    if side == "long":
        depth = sum(float(price) * float(amount) for price, amount in levels if float(price) <= ref_price * (1 + band_pct))
    else:
        depth = sum(float(price) * float(amount) for price, amount in levels if float(price) >= ref_price * (1 - band_pct))

    required = abs(notional) * getattr(config, "MIN_DEPTH_TO_NOTIONAL_MULT", 3.0)
    if depth < required:
        return GuardDecision(False, f"thin_book:{depth:.2f}<{required:.2f}")

    return GuardDecision(True, f"spread={spread_pct:.5f},depth={depth:.2f}")


def _get(bar, key: str):
    if isinstance(bar, dict):
        return bar.get(key)
    return bar[key]


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
