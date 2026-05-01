"""
Passive TWAP planning helper.

This module only creates deterministic slice plans. It does not place orders.
Live/testnet wiring must be added separately after fill-quality tests.
"""

from __future__ import annotations

from dataclasses import dataclass

import config

PASSIVE_ONLY = True
LIVE_ORDER_FLOW_WIRED = False


@dataclass(frozen=True)
class TwapSlice:
    index: int
    delay_seconds: int
    notional: float
    amount: float


def raise_if_live_execution_requested() -> None:
    raise NotImplementedError(
        "twap_execution.py is a passive slice planner only; it is not wired to "
        "live/testnet order placement."
    )


def should_twap(notional: float, *, enabled: bool | None = None) -> bool:
    active = getattr(config, "TWAP_ENABLED", False) if enabled is None else enabled
    return active and float(notional) >= float(getattr(config, "TWAP_MIN_NOTIONAL_USDT", 5_000.0))


def build_twap_plan(
    *,
    notional: float,
    price: float,
    enabled: bool | None = None,
    slice_notional: float | None = None,
    max_slices: int | None = None,
    interval_seconds: int | None = None,
) -> list[TwapSlice]:
    if price <= 0 or notional <= 0:
        return []
    if not should_twap(notional, enabled=enabled):
        return [TwapSlice(1, 0, round(float(notional), 6), round(float(notional) / float(price), 8))]

    target_slice = float(slice_notional or getattr(config, "TWAP_SLICE_NOTIONAL_USDT", 1_000.0))
    max_count = max(1, int(max_slices or getattr(config, "TWAP_MAX_SLICES", 10)))
    interval = max(0, int(interval_seconds or getattr(config, "TWAP_INTERVAL_SECONDS", 30)))
    count = min(max_count, max(1, int((float(notional) + target_slice - 1) // target_slice)))

    base = float(notional) / count
    slices: list[TwapSlice] = []
    remaining = float(notional)
    for idx in range(1, count + 1):
        slice_value = base if idx < count else remaining
        remaining -= slice_value
        slices.append(
            TwapSlice(
                index=idx,
                delay_seconds=(idx - 1) * interval,
                notional=round(slice_value, 6),
                amount=round(slice_value / float(price), 8),
            )
        )
    return slices
