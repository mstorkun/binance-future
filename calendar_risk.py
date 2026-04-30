"""
Calendar and session risk controls.

This module does not try to predict event outcomes. It only reduces or blocks
new entries around known high-risk windows: weekends, funding timestamps, daily
candle close/open, and manually maintained macro events.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

import config


@dataclass(frozen=True)
class CalendarRiskDecision:
    multiplier: float
    block_new_entries: bool
    reasons: tuple[str, ...]


def _as_utc_naive(ts) -> pd.Timestamp | None:
    if ts is None:
        return None
    out = pd.Timestamp(ts)
    if pd.isna(out):
        return None
    if out.tzinfo is not None:
        out = out.tz_convert("UTC").tz_localize(None)
    return out


def _timeframe_delta(timeframe: str | None = None) -> pd.Timedelta:
    tf = (timeframe or getattr(config, "TIMEFRAME", "4h")).lower()
    if tf.endswith("m"):
        return pd.Timedelta(minutes=int(tf[:-1]))
    if tf.endswith("h"):
        return pd.Timedelta(hours=int(tf[:-1]))
    if tf.endswith("d"):
        return pd.Timedelta(days=int(tf[:-1]))
    return pd.Timedelta(hours=4)


def _near_hour(ts: pd.Timestamp, target_hours: set[int], window_minutes: int) -> bool:
    if window_minutes <= 0:
        return False
    candidates = []
    day_start = ts.normalize()
    for offset in (-1, 0, 1):
        base = day_start + pd.Timedelta(days=offset)
        for hour in target_hours:
            candidates.append(base + pd.Timedelta(hours=hour))
    return min(abs((ts - candidate).total_seconds()) for candidate in candidates) <= window_minutes * 60


def _event_decision(ts: pd.Timestamp) -> CalendarRiskDecision:
    event_file = Path(getattr(config, "CALENDAR_EVENT_FILE", "event_calendar.csv"))
    if not event_file.exists():
        return CalendarRiskDecision(1.0, False, ())

    try:
        events = pd.read_csv(event_file)
    except Exception:
        return CalendarRiskDecision(1.0, False, ("event_calendar_unreadable",))

    if events.empty or "timestamp_utc" not in events.columns:
        return CalendarRiskDecision(1.0, False, ())

    multiplier = 1.0
    block = False
    reasons: list[str] = []
    for _, event in events.iterrows():
        event_ts = _as_utc_naive(event.get("timestamp_utc"))
        if event_ts is None:
            continue

        pre = int(event.get("pre_minutes", 0) or 0)
        post = int(event.get("post_minutes", 0) or 0)
        if event_ts - pd.Timedelta(minutes=pre) <= ts <= event_ts + pd.Timedelta(minutes=post):
            risk_mult = float(event.get("risk_mult", 1.0) or 1.0)
            multiplier *= risk_mult
            should_block = str(event.get("block_new_entries", "")).strip().lower() in {"1", "true", "yes", "y"}
            block = block or should_block
            name = str(event.get("event", "calendar_event")).strip() or "calendar_event"
            impact = str(event.get("impact", "")).strip()
            reasons.append(f"event:{name}{':' + impact if impact else ''}")

    return CalendarRiskDecision(multiplier, block, tuple(reasons))


def calendar_risk_decision(ts, timeframe: str | None = None) -> CalendarRiskDecision:
    if not getattr(config, "CALENDAR_RISK_ENABLED", True):
        return CalendarRiskDecision(1.0, False, ())

    opened_at = _as_utc_naive(ts)
    if opened_at is None:
        return CalendarRiskDecision(1.0, False, ())

    # Signal bars are stored by open time; use close time for funding/daily close checks.
    closed_at = opened_at + _timeframe_delta(timeframe)

    multiplier = 1.0
    reasons: list[str] = []
    block = False

    if closed_at.weekday() in (5, 6):
        multiplier *= getattr(config, "WEEKEND_RISK_MULT", 0.70)
        reasons.append("weekend")

    # CME crypto futures weekly reopen often affects crypto liquidity and gaps.
    if closed_at.weekday() == 0 and closed_at.hour < 4:
        multiplier *= getattr(config, "WEEKLY_OPEN_RISK_MULT", 0.75)
        reasons.append("weekly_open")

    if _near_hour(closed_at, {0, 8, 16}, getattr(config, "FUNDING_WINDOW_MINUTES", 30)):
        multiplier *= getattr(config, "FUNDING_RISK_MULT", 0.90)
        reasons.append("funding_window")

    if _near_hour(closed_at, {0}, getattr(config, "DAILY_CLOSE_WINDOW_MINUTES", 60)):
        multiplier *= getattr(config, "DAILY_CLOSE_RISK_MULT", 0.85)
        reasons.append("daily_close")

    event = _event_decision(closed_at)
    multiplier *= event.multiplier
    block = block or event.block_new_entries
    reasons.extend(event.reasons)

    return CalendarRiskDecision(multiplier, block, tuple(reasons))
