"""
Passive mature-bot protection layer.

This module mirrors the useful parts of mature bot platforms without changing
the current strategy by default. It only becomes decision-active when
config.PROTECTIONS_ENABLED is True.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import pandas as pd

import config


@dataclass(frozen=True)
class ProtectionDecision:
    multiplier: float
    block_new_entries: bool
    reasons: tuple[str, ...]
    locked_until: pd.Timestamp | None = None


def _timeframe_minutes(timeframe: str | None = None) -> float:
    tf = timeframe or getattr(config, "TIMEFRAME", "4h")
    unit = tf[-1]
    value = int(tf[:-1])
    if unit == "m":
        return float(value)
    if unit == "h":
        return float(value * 60)
    if unit == "d":
        return float(value * 24 * 60)
    if unit == "w":
        return float(value * 7 * 24 * 60)
    return 240.0


def _minutes(candles: int | float) -> float:
    return float(candles) * _timeframe_minutes()


def _ts(value) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    try:
        out = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(out):
        return None
    return out.tz_localize(None) if out.tzinfo is not None else out


def _rows(trades: Iterable[Mapping[str, Any]] | pd.DataFrame | None) -> list[dict[str, Any]]:
    if trades is None:
        return []
    if isinstance(trades, pd.DataFrame):
        return trades.to_dict("records")
    return [dict(row) for row in trades]


def _exit_time(row: Mapping[str, Any]) -> pd.Timestamp | None:
    return _ts(row.get("exit_time") or row.get("closed_at") or row.get("timestamp") or row.get("time"))


def _pnl(row: Mapping[str, Any]) -> float:
    try:
        return float(row.get("pnl", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _is_stop_loss(row: Mapping[str, Any]) -> bool:
    reason = str(row.get("result") or row.get("exit_reason") or "").lower()
    return _pnl(row) <= 0 and ("sl" in reason or "stop" in reason)


def _recent(now: pd.Timestamp, trades: list[dict[str, Any]], lookback_minutes: float) -> list[dict[str, Any]]:
    start = now - pd.Timedelta(minutes=lookback_minutes)
    out: list[dict[str, Any]] = []
    for row in trades:
        ts = _exit_time(row)
        if ts is not None and start <= ts <= now:
            out.append(row)
    return out


def protection_decision(
    symbol: str,
    now,
    closed_trades: Iterable[Mapping[str, Any]] | pd.DataFrame | None = None,
    *,
    equity: float | None = None,
    peak_equity: float | None = None,
) -> ProtectionDecision:
    """Return a new-entry protection decision for a symbol.

    With PROTECTIONS_ENABLED=False, this is neutral so current profitability
    and trade count are unchanged.
    """
    if not getattr(config, "PROTECTIONS_ENABLED", False):
        return ProtectionDecision(1.0, False, ())

    now_ts = _ts(now)
    if now_ts is None:
        return ProtectionDecision(1.0, False, ("protection:no_time",))

    trades = _rows(closed_trades)
    reasons: list[str] = []
    locked_until: pd.Timestamp | None = None

    symbol_trades = [row for row in trades if row.get("symbol") == symbol]
    if symbol_trades:
        exit_times = [ts for ts in (_exit_time(row) for row in symbol_trades) if ts is not None]
        last_exit = max(exit_times) if exit_times else None
        if last_exit is not None:
            cooldown_until = last_exit + pd.Timedelta(
                minutes=_minutes(getattr(config, "PROTECTION_COOLDOWN_CANDLES", 1))
            )
            if now_ts < cooldown_until:
                reasons.append("protection:cooldown")
                locked_until = cooldown_until

    recent_all = _recent(now_ts, trades, _minutes(getattr(config, "PROTECTION_STOPLOSS_LOOKBACK_CANDLES", 24)))
    stop_count = sum(1 for row in recent_all if _is_stop_loss(row))
    if stop_count >= int(getattr(config, "PROTECTION_STOPLOSS_TRADE_LIMIT", 3)):
        reasons.append("protection:stoploss_guard")
        stop_until = now_ts + pd.Timedelta(minutes=_minutes(getattr(config, "PROTECTION_STOPLOSS_LOCK_CANDLES", 2)))
        locked_until = max(locked_until, stop_until) if locked_until is not None else stop_until

    recent_pair = _recent(now_ts, symbol_trades, _minutes(getattr(config, "PROTECTION_LOW_PROFIT_LOOKBACK_CANDLES", 12)))
    if len(recent_pair) >= int(getattr(config, "PROTECTION_LOW_PROFIT_TRADE_LIMIT", 3)):
        pair_pnl = sum(_pnl(row) for row in recent_pair)
        required = float(getattr(config, "PROTECTION_LOW_PROFIT_REQUIRED_PNL", 0.0))
        if pair_pnl <= required:
            reasons.append("protection:low_profit_pair")
            pair_until = now_ts + pd.Timedelta(minutes=_minutes(getattr(config, "PROTECTION_LOW_PROFIT_LOCK_CANDLES", 2)))
            locked_until = max(locked_until, pair_until) if locked_until is not None else pair_until

    if equity is not None and peak_equity is not None and peak_equity > 0:
        dd = (peak_equity - equity) / peak_equity
        if dd >= float(getattr(config, "PROTECTION_MAX_DRAWDOWN_PCT", 0.15)):
            reasons.append("protection:max_drawdown")
            dd_until = now_ts + pd.Timedelta(minutes=_minutes(getattr(config, "PROTECTION_MAX_DRAWDOWN_LOCK_CANDLES", 6)))
            locked_until = max(locked_until, dd_until) if locked_until is not None else dd_until

    if reasons:
        return ProtectionDecision(0.0, True, tuple(reasons), locked_until)
    return ProtectionDecision(1.0, False, ())
