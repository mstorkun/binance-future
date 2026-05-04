from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import config


@dataclass(frozen=True)
class UrgentExitDecision:
    market_exit: bool
    reason: str = ""
    exit_price: float | None = None
    urgency_score: float = 0.0
    loss_r: float = 0.0
    equity_loss_pct: float = 0.0
    reasons: tuple[str, ...] = ()


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        return obj[key]
    except Exception:
        return getattr(obj, key, default)


def _num(value: Any, default: float | None = 0.0) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _risk_distance(position: dict[str, Any], entry: float, atr: float | None) -> float:
    stop = _num(position.get("sl"), None)
    if stop is not None and stop > 0:
        distance = abs(entry - stop)
        if distance > 0:
            return distance
    atr_distance = (atr or 0.0) * float(getattr(config, "SL_ATR_MULT", 2.0))
    return max(float(atr_distance), entry * 0.002)


def _equity_loss_pct(position: dict[str, Any], adverse_price_move: float) -> float:
    size = _num(position.get("size"), 0.0) or 0.0
    equity = _num(position.get("entry_equity"), 0.0) or 0.0
    if size <= 0 or equity <= 0:
        return 0.0
    return max(0.0, adverse_price_move * size / equity * 100.0)


def thesis_invalid(position: dict[str, Any], bar: Any) -> tuple[bool, tuple[str, ...]]:
    side = str(position.get("side", "")).lower()
    reasons: list[str] = []
    daily = _num(_get(bar, "daily_trend"), None)
    weekly = _num(_get(bar, "weekly_trend"), None)
    adx = _num(_get(bar, "adx"), None)
    close = _num(_get(bar, "close"), None)
    exit_low = _num(_get(bar, "donchian_exit_low"), None)
    exit_high = _num(_get(bar, "donchian_exit_high"), None)
    ema_fast = _num(_get(bar, "ema_fast"), None)
    ema_slow = _num(_get(bar, "ema_slow"), None)
    regime = str(_get(bar, "regime", "") or "").lower()

    if side == "long":
        if daily == -1:
            reasons.append("thesis:daily_against")
        if weekly == -1:
            reasons.append("thesis:weekly_against")
        if close is not None and exit_low is not None and close < exit_low:
            reasons.append("thesis:donchian_exit")
        if close is not None and ema_fast is not None and ema_slow is not None and close < ema_fast < ema_slow:
            reasons.append("thesis:ema_stack_against")
    elif side == "short":
        if daily == 1:
            reasons.append("thesis:daily_against")
        if weekly == 1:
            reasons.append("thesis:weekly_against")
        if close is not None and exit_high is not None and close > exit_high:
            reasons.append("thesis:donchian_exit")
        if close is not None and ema_fast is not None and ema_slow is not None and close > ema_fast > ema_slow:
            reasons.append("thesis:ema_stack_against")

    if regime == "trend" and adx is not None and adx >= float(getattr(config, "ADX_THRESH", 20)):
        strong_against = any(reason in reasons for reason in ("thesis:daily_against", "thesis:ema_stack_against", "thesis:donchian_exit"))
        if strong_against:
            reasons.append("thesis:strong_adverse_trend")

    return bool(reasons), tuple(dict.fromkeys(reasons))


def thesis_supportive(position: dict[str, Any], bar: Any) -> tuple[bool, tuple[str, ...]]:
    side = str(position.get("side", "")).lower()
    reasons: list[str] = []
    daily = _num(_get(bar, "daily_trend"), None)
    weekly = _num(_get(bar, "weekly_trend"), None)
    adx = _num(_get(bar, "adx"), None)
    close = _num(_get(bar, "close"), None)
    ema_fast = _num(_get(bar, "ema_fast"), None)
    ema_slow = _num(_get(bar, "ema_slow"), None)
    regime = str(_get(bar, "regime", "") or "").lower()
    candle_bias = _num(_get(bar, "candle_bias"), _num(_get(bar, "candle_structure_bias"), None))
    mtf_bias = str(_get(bar, "mtf_bias", "") or "").lower()
    news_bias = str(_get(bar, "news_bias", "") or _get(bar, "trade_bias", "") or "").lower()
    event_action = str(_get(bar, "event_action", "") or _get(bar, "calendar_action", "") or "").lower()

    expected_trend = 1 if side == "long" else -1
    expected_bias = "long" if side == "long" else "short"

    if daily == expected_trend:
        reasons.append("support:daily")
    if weekly == expected_trend:
        reasons.append("support:weekly")
    if close is not None and ema_fast is not None and ema_slow is not None:
        if (side == "long" and close > ema_fast > ema_slow) or (side == "short" and close < ema_fast < ema_slow):
            reasons.append("support:ema_stack")
    if regime == "trend" and adx is not None and adx >= float(getattr(config, "ADX_THRESH", 20)):
        reasons.append("support:trend_regime")
    if candle_bias == expected_trend:
        reasons.append("support:candle")
    if mtf_bias == expected_bias:
        reasons.append("support:mtf")
    if news_bias in {"", "wait", "neutral", expected_bias}:
        if news_bias == expected_bias:
            reasons.append("support:news")
    elif news_bias:
        return False, tuple(dict.fromkeys(reasons + ["support:news_against"]))
    if event_action in {"block_new_entries", "observe_only", "symbol_observe_only"}:
        return False, tuple(dict.fromkeys(reasons + ["support:event_risk"]))

    min_reasons = int(getattr(config, "URGENT_EXIT_HOLD_SUPPORT_MIN_REASONS", 2))
    return len(reasons) >= min_reasons, tuple(dict.fromkeys(reasons))


def urgent_exit_decision(position: dict[str, Any], bar: Any) -> UrgentExitDecision:
    """Decide when commission is secondary and a reduce-only market exit is needed.

    This is intentionally stricter than "position is red". It requires real loss
    plus either stop/liquidation proximity or adverse momentum confirmation.
    """
    if not getattr(config, "URGENT_EXIT_ENABLED", True):
        return UrgentExitDecision(False, reason="urgent_exit_disabled")

    side = str(position.get("side", "")).lower()
    if side not in {"long", "short"}:
        return UrgentExitDecision(False, reason="bad_side")

    entry = _num(position.get("entry"), None)
    close = _num(_get(bar, "close"), None)
    open_ = _num(_get(bar, "open"), close)
    high = _num(_get(bar, "high"), close)
    low = _num(_get(bar, "low"), close)
    atr = _num(_get(bar, "atr"), _num(position.get("atr"), None))
    if entry is None or close is None or open_ is None or high is None or low is None or entry <= 0:
        return UrgentExitDecision(False, reason="insufficient_price_data")

    if side == "long":
        adverse_move = max(0.0, entry - close)
        adverse_extreme = max(0.0, entry - low)
        candle_against = close < open_
        close_location = (close - low) / max(high - low, entry * 1e-9)
        opposite_close_location = close_location <= 0.35
        liq = _num(position.get("liquidation_price"), None)
        liq_distance_pct = ((close - liq) / close) if liq is not None and liq > 0 else None
    else:
        adverse_move = max(0.0, close - entry)
        adverse_extreme = max(0.0, high - entry)
        candle_against = close > open_
        close_location = (close - low) / max(high - low, entry * 1e-9)
        opposite_close_location = close_location >= 0.65
        liq = _num(position.get("liquidation_price"), None)
        liq_distance_pct = ((liq - close) / close) if liq is not None and liq > 0 else None

    risk_distance = _risk_distance(position, entry, atr)
    loss_r = adverse_move / max(risk_distance, entry * 1e-9)
    adverse_extreme_r = adverse_extreme / max(risk_distance, entry * 1e-9)
    equity_loss = _equity_loss_pct(position, adverse_move)
    invalid, thesis_reasons = thesis_invalid(position, bar)
    supportive, support_reasons = thesis_supportive(position, bar)

    min_loss_r = float(getattr(config, "URGENT_EXIT_MIN_LOSS_R", 0.70))
    min_equity_loss = float(getattr(config, "URGENT_EXIT_MIN_EQUITY_LOSS_PCT", 0.75))
    max_equity_loss = float(getattr(config, "URGENT_EXIT_MAX_EQUITY_LOSS_PCT", 30.0))
    absolute_equity_loss = float(getattr(config, "URGENT_EXIT_ABSOLUTE_EQUITY_LOSS_PCT", 50.0))
    has_real_loss = loss_r >= min_loss_r or equity_loss >= min_equity_loss
    if equity_loss >= absolute_equity_loss:
        return UrgentExitDecision(
            True,
            reason="urgent_market_exit",
            exit_price=close,
            urgency_score=20.0,
            loss_r=round(float(loss_r), 4),
            equity_loss_pct=round(float(equity_loss), 4),
            reasons=("urgent:absolute_equity_loss",) + thesis_reasons,
        )
    if equity_loss >= max_equity_loss and invalid:
        return UrgentExitDecision(
            True,
            reason="urgent_market_exit",
            exit_price=close,
            urgency_score=10.0,
            loss_r=round(float(loss_r), 4),
            equity_loss_pct=round(float(equity_loss), 4),
            reasons=("urgent:max_thesis_loss",) + thesis_reasons,
        )
    if equity_loss >= max_equity_loss and supportive:
        return UrgentExitDecision(
            False,
            reason="large_loss_thesis_supported_hold",
            exit_price=close,
            urgency_score=0.0,
            loss_r=round(float(loss_r), 4),
            equity_loss_pct=round(float(equity_loss), 4),
            reasons=support_reasons,
        )
    if equity_loss >= max_equity_loss:
        return UrgentExitDecision(
            True,
            reason="urgent_market_exit",
            exit_price=close,
            urgency_score=8.0,
            loss_r=round(float(loss_r), 4),
            equity_loss_pct=round(float(equity_loss), 4),
            reasons=("urgent:max_context_loss",) + support_reasons,
        )
    if not has_real_loss:
        return UrgentExitDecision(
            False,
            reason="loss_not_urgent",
            exit_price=close,
            loss_r=round(float(loss_r), 4),
            equity_loss_pct=round(float(equity_loss), 4),
        )

    reasons: list[str] = []
    score = 0.0

    if invalid:
        score += 0.6
        reasons.extend(thesis_reasons)

    force_loss_r = float(getattr(config, "URGENT_EXIT_FORCE_LOSS_R", 1.15))
    if loss_r >= force_loss_r and invalid:
        score += 1.2
        reasons.append("urgent:loss_r")

    if adverse_extreme_r >= force_loss_r and candle_against and invalid:
        score += 0.7
        reasons.append("urgent:adverse_extreme")

    bar_range = max(high - low, 0.0)
    range_atr = bar_range / max(float(atr or 0.0), entry * 1e-9)
    volume = _num(_get(bar, "volume"), None)
    volume_ma = _num(_get(bar, "volume_ma"), None)
    volume_ratio = (volume / volume_ma) if volume is not None and volume_ma and volume_ma > 0 else 1.0
    if (
        invalid
        and
        candle_against
        and opposite_close_location
        and range_atr >= float(getattr(config, "URGENT_EXIT_RANGE_ATR_MULT", 1.20))
        and volume_ratio >= float(getattr(config, "URGENT_EXIT_VOLUME_MULT", 1.30))
    ):
        score += 1.0
        reasons.append("urgent:adverse_momentum")

    if liq_distance_pct is not None and liq_distance_pct > 0:
        liq_buffer = float(getattr(config, "URGENT_EXIT_LIQUIDATION_BUFFER_PCT", 0.03))
        atr_pct = float(atr or 0.0) / close if close > 0 else 0.0
        if liq_distance_pct <= max(liq_buffer, atr_pct * 2.0):
            score += 1.3
            reasons.append("urgent:liquidation_buffer")

    threshold = float(getattr(config, "URGENT_EXIT_SCORE_THRESHOLD", 1.0))
    if score >= threshold:
        return UrgentExitDecision(
            True,
            reason="urgent_market_exit",
            exit_price=close,
            urgency_score=round(float(score), 4),
            loss_r=round(float(loss_r), 4),
            equity_loss_pct=round(float(equity_loss), 4),
            reasons=tuple(reasons),
        )

    return UrgentExitDecision(
        False,
        reason="thesis_valid_hold" if not invalid else "loss_but_not_urgent",
        exit_price=close,
        urgency_score=round(float(score), 4),
        loss_r=round(float(loss_r), 4),
        equity_loss_pct=round(float(equity_loss), 4),
        reasons=tuple(dict.fromkeys(reasons)) if reasons else ("thesis:valid",),
    )
