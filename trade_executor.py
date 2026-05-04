"""
Passive trade lifecycle model inspired by executor-based bot frameworks.

The current live/paper code does not call this module. It gives future work a
small, testable contract for entry, protection, trailing, partial exits, and
final close without rewriting the strategy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd

import config
import execution_guard as eg
import exit_ladder
import strategy as strat
import urgent_exit_policy

PASSIVE_ONLY = True
LIVE_ORDER_FLOW_WIRED = False


class ExecutorStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    CLOSED = "closed"
    FAILED = "failed"


def raise_if_live_execution_requested() -> None:
    raise NotImplementedError(
        "trade_executor.py is a passive lifecycle model only; it is not wired "
        "to live/testnet order placement."
    )


@dataclass
class ManagedTrade:
    symbol: str
    side: str
    entry: float
    size: float
    atr: float
    entry_time: object
    sl: float
    hard_sl: float
    liquidation_price: float | None = None
    extreme: float | None = None
    status: ExecutorStatus = ExecutorStatus.CREATED
    filled_exit_steps: int = 0
    remaining_size: float | None = None
    events: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if self.extreme is None:
            self.extreme = self.entry
        if self.remaining_size is None:
            self.remaining_size = self.size

    def activate(self) -> None:
        self.status = ExecutorStatus.ACTIVE
        self.events.append({"event": "activated", "time": pd.Timestamp(self.entry_time).isoformat()})

    def update_from_bar(self, bar) -> list[dict]:
        if self.status != ExecutorStatus.ACTIVE:
            return []
        bar = _guard_ready_bar(bar)

        emitted: list[dict] = []
        stop_decision = eg.stop_decision(self.__dict__, bar)
        if stop_decision.hit:
            if not (str(stop_decision.reason).startswith("soft_sl") and getattr(config, "THESIS_HOLD_SOFT_STOP_ENABLED", True)):
                self.status = ExecutorStatus.CLOSED
                event = {"event": "close", "reason": stop_decision.reason, "price": stop_decision.price}
                self.events.append(event)
                return [event]
            urgent = urgent_exit_policy.urgent_exit_decision(self.__dict__, bar)
            if urgent.market_exit:
                self.status = ExecutorStatus.CLOSED
                event = {
                    "event": "close",
                    "reason": urgent.reason,
                    "price": urgent.exit_price,
                    "order_type": "reduce_only_market",
                    "urgent_exit_reasons": "|".join(urgent.reasons),
                }
                self.events.append(event)
                return [event]
            self.events.append({
                "event": "soft_stop_hold",
                "reason": urgent.reason,
                "loss_r": urgent.loss_r,
                "equity_loss_pct": urgent.equity_loss_pct,
            })

        urgent = urgent_exit_policy.urgent_exit_decision(self.__dict__, bar)
        if urgent.market_exit:
            self.status = ExecutorStatus.CLOSED
            event = {
                "event": "close",
                "reason": urgent.reason,
                "price": urgent.exit_price,
                "order_type": "reduce_only_market",
                "urgent_exit_reasons": "|".join(urgent.reasons),
            }
            self.events.append(event)
            return [event]

        plan = exit_ladder.build_exit_plan(self.entry, self.atr, self.side, enabled=getattr(config, "EXIT_LADDER_ENABLED", False))
        while self.filled_exit_steps < len(plan):
            step = plan[self.filled_exit_steps]
            hit = (
                self.side == strat.LONG and float(bar["high"]) >= step.target
            ) or (
                self.side == strat.SHORT and float(bar["low"]) <= step.target
            )
            if not hit:
                break
            close_size = float(self.size) * step.close_fraction
            self.remaining_size = max(0.0, float(self.remaining_size or 0.0) - close_size)
            self.filled_exit_steps += 1
            new_stop = exit_ladder.stop_after_filled_steps(self.entry, self.side, plan, self.filled_exit_steps)
            if new_stop is not None:
                self.sl = new_stop
                self.hard_sl = eg.hard_stop_from_soft(self.sl, self.atr, self.side)
            event = {
                "event": "partial_close",
                "step": step.name,
                "price": step.target,
                "size": close_size,
                "remaining_size": self.remaining_size,
                "new_sl": self.sl,
            }
            self.events.append(event)
            emitted.append(event)

        if not eg.should_skip_trailing_update(bar).ok:
            return emitted
        if self.side == strat.LONG:
            self.extreme = max(float(self.extreme), float(bar["high"]))
            new_sl = strat.trailing_stop(self.entry, float(self.extreme), self.side, self.atr)
            if new_sl > self.sl:
                self.sl = new_sl
                self.hard_sl = eg.hard_stop_from_soft(new_sl, self.atr, self.side)
        else:
            self.extreme = min(float(self.extreme), float(bar["low"]))
            new_sl = strat.trailing_stop(self.entry, float(self.extreme), self.side, self.atr)
            if new_sl < self.sl:
                self.sl = new_sl
                self.hard_sl = eg.hard_stop_from_soft(new_sl, self.atr, self.side)
        return emitted


def _guard_ready_bar(bar):
    """Fill optional guard fields for unit-level executor simulations."""
    if hasattr(bar, "copy"):
        out = bar.copy()
        if "volume_ma" not in out:
            out["volume_ma"] = out.get("volume", 0.0)
        return out
    return bar
