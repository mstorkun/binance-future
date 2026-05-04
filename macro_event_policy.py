from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class MacroEventPolicy:
    category: str
    impact: str
    pre_minutes: int
    post_minutes: int
    risk_mult: float
    block_new_entries: bool
    action: str


POLICIES: tuple[MacroEventPolicy, ...] = (
    MacroEventPolicy("fomc", "critical", 240, 360, 0.0, True, "observe_only"),
    MacroEventPolicy("fed_speech", "high", 120, 180, 0.25, True, "observe_only"),
    MacroEventPolicy("cpi", "critical", 180, 240, 0.0, True, "observe_only"),
    MacroEventPolicy("nfp", "critical", 180, 240, 0.0, True, "observe_only"),
    MacroEventPolicy("employment", "critical", 180, 240, 0.0, True, "observe_only"),
    MacroEventPolicy("pce", "high", 180, 240, 0.0, True, "observe_only"),
    MacroEventPolicy("ppi", "high", 120, 180, 0.20, True, "observe_only"),
    MacroEventPolicy("gdp", "medium", 90, 180, 0.35, False, "reduce_risk"),
    MacroEventPolicy("jolts", "medium", 60, 120, 0.50, False, "reduce_risk"),
    MacroEventPolicy("treasury", "medium", 60, 120, 0.50, False, "reduce_risk"),
    MacroEventPolicy("binance_maintenance", "high", 120, 240, 0.0, True, "observe_only"),
    MacroEventPolicy("binance_listing", "symbol_high", 60, 240, 0.0, True, "symbol_observe_only"),
    MacroEventPolicy("binance_delisting", "symbol_critical", 1440, 2880, 0.0, True, "symbol_observe_only"),
    MacroEventPolicy("stablecoin_depeg", "critical", 0, 1440, 0.0, True, "observe_only"),
    MacroEventPolicy("exchange_outage", "critical", 0, 1440, 0.0, True, "observe_only"),
    MacroEventPolicy("hack_exploit", "critical", 0, 1440, 0.0, True, "observe_only"),
)


KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("fomc", ("fomc", "federal open market", "rate decision", "fed decision", "summary of economic projections")),
    ("fed_speech", ("powell", "fed chair", "federal reserve speech", "fed testimony", "fed minutes")),
    ("cpi", ("consumer price index", " cpi", "inflation")),
    ("ppi", ("producer price index", " ppi")),
    ("pce", ("personal income and outlays", " pce", "personal consumption expenditures")),
    ("nfp", ("nonfarm payroll", "payrolls", "employment situation", "unemployment")),
    ("gdp", ("gross domestic product", " gdp")),
    ("jolts", ("job openings", "jolts")),
    ("treasury", ("treasury refunding", "treasury auction", "us treasury")),
    ("binance_maintenance", ("binance maintenance", "system upgrade", "wallet maintenance")),
    ("binance_listing", ("binance will list", "new listing", "launchpool", "listing")),
    ("binance_delisting", ("delist", "remove and cease trading", "trading pairs will be removed")),
    ("stablecoin_depeg", ("depeg", "de-pegged", "stablecoin loses peg")),
    ("exchange_outage", ("outage", "withdrawals suspended", "trading suspended")),
    ("hack_exploit", ("hack", "exploit", "breach", "security incident")),
)


def classify_event(name: str, *, category: str = "") -> MacroEventPolicy:
    text = f"{category} {name}".strip().lower()
    for key, needles in KEYWORDS:
        if any(needle in text for needle in needles):
            return policy_for_category(key)
    return MacroEventPolicy("unknown", "low", 0, 60, 0.75, False, "reduce_risk")


def policy_for_category(category: str) -> MacroEventPolicy:
    normalized = str(category).strip().lower()
    for policy in POLICIES:
        if policy.category == normalized:
            return policy
    return MacroEventPolicy(normalized or "unknown", "low", 0, 60, 0.75, False, "reduce_risk")


def event_calendar_row(timestamp_utc, event: str, *, category: str = "", source: str = "") -> dict[str, object]:
    policy = classify_event(event, category=category)
    ts = pd.Timestamp(timestamp_utc)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return {
        "timestamp_utc": ts.isoformat(sep=" "),
        "event": event,
        "impact": policy.impact,
        "pre_minutes": policy.pre_minutes,
        "post_minutes": policy.post_minutes,
        "risk_mult": policy.risk_mult,
        "block_new_entries": str(policy.block_new_entries).lower(),
        "action": policy.action,
        "source": source,
    }


def build_event_calendar_rows(events: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return [
        event_calendar_row(
            event.get("timestamp_utc"),
            str(event.get("event", "")),
            category=str(event.get("category", "")),
            source=str(event.get("source", "")),
        )
        for event in events
        if event.get("timestamp_utc") and event.get("event")
    ]
