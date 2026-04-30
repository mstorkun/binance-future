"""
Passive partial-take-profit and breakeven helper.

The current bot does not use this module unless EXIT_LADDER_ENABLED is turned
on and explicitly wired into a runner. Keeping it separate lets us backtest the
exit management layer without changing today's strategy.
"""

from __future__ import annotations

from dataclasses import dataclass

import config
import strategy as strat


@dataclass(frozen=True)
class ExitStep:
    name: str
    r_multiple: float
    target: float
    close_fraction: float


def risk_distance(atr: float) -> float:
    return float(atr) * float(config.SL_ATR_MULT)


def target_for_r(entry: float, atr: float, side: str, r_multiple: float) -> float:
    distance = risk_distance(atr) * float(r_multiple)
    if side == strat.LONG:
        return float(entry) + distance
    return float(entry) - distance


def build_exit_plan(entry: float, atr: float, side: str, *, enabled: bool | None = None) -> list[ExitStep]:
    active = getattr(config, "EXIT_LADDER_ENABLED", False) if enabled is None else enabled
    if not active:
        return []

    tp1_fraction = max(0.0, min(1.0, float(getattr(config, "EXIT_LADDER_TP1_FRACTION", 0.25))))
    tp2_fraction = max(0.0, min(1.0 - tp1_fraction, float(getattr(config, "EXIT_LADDER_TP2_FRACTION", 0.25))))

    steps = [
        ExitStep(
            "tp1",
            float(getattr(config, "EXIT_LADDER_TP1_R", 1.0)),
            target_for_r(entry, atr, side, getattr(config, "EXIT_LADDER_TP1_R", 1.0)),
            tp1_fraction,
        ),
        ExitStep(
            "tp2",
            float(getattr(config, "EXIT_LADDER_TP2_R", 2.0)),
            target_for_r(entry, atr, side, getattr(config, "EXIT_LADDER_TP2_R", 2.0)),
            tp2_fraction,
        ),
    ]
    return [step for step in steps if step.close_fraction > 0]


def stop_after_filled_steps(entry: float, side: str, plan: list[ExitStep], filled_steps: int) -> float | None:
    """Return the protective stop implied by filled TP steps."""
    if filled_steps < int(getattr(config, "EXIT_LADDER_BREAKEVEN_AFTER_STEP", 1)):
        return None
    if filled_steps <= 1:
        return float(entry)
    prev_index = min(filled_steps - 2, max(len(plan) - 1, 0))
    return float(plan[prev_index].target) if plan else float(entry)
