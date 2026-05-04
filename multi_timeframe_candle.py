from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class MultiTimeframeCandleDecision:
    multiplier: float
    block_new_entries: bool
    permission: str
    bias: str
    confidence: float
    reasons: tuple[str, ...]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(_num(value, 0.0))


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    return pd.to_numeric(num / den.replace(0, pd.NA), errors="coerce")


def _true_range(df: pd.DataFrame) -> pd.Series:
    return pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)


def add_candle_context_features(
    df: pd.DataFrame,
    *,
    prefix: str = "",
    lookback: int = 20,
) -> pd.DataFrame:
    """Create closed-candle context features for multi-timeframe gating."""
    out = pd.DataFrame(index=df.index)
    if df.empty:
        return out

    open_ = pd.to_numeric(df["open"], errors="coerce")
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce")

    candle_range = (high - low).replace(0, pd.NA)
    body_signed = close - open_
    body_abs = body_signed.abs()
    upper_wick = high - pd.concat([open_, close], axis=1).max(axis=1)
    lower_wick = pd.concat([open_, close], axis=1).min(axis=1) - low
    direction = body_signed.apply(lambda value: 1 if value > 0 else (-1 if value < 0 else 0))
    tr = _true_range(df)
    atr = tr.ewm(alpha=1.0 / 14.0, adjust=False).mean().replace(0, pd.NA)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    prior_open = open_.shift(1)
    prior_close = close.shift(1)
    prior_high = high.shift(1)
    prior_low = low.shift(1)
    prior_body_high = pd.concat([prior_open, prior_close], axis=1).max(axis=1)
    prior_body_low = pd.concat([prior_open, prior_close], axis=1).min(axis=1)
    body_high = pd.concat([open_, close], axis=1).max(axis=1)
    body_low = pd.concat([open_, close], axis=1).min(axis=1)

    lookback = max(5, int(lookback))
    range_median = candle_range.rolling(lookback, min_periods=max(3, lookback // 3)).median()
    volume_median = volume.rolling(lookback, min_periods=max(3, lookback // 3)).median()
    recent_high = high.rolling(lookback, min_periods=max(3, lookback // 3)).max().shift(1)
    recent_low = low.rolling(lookback, min_periods=max(3, lookback // 3)).min().shift(1)

    p = prefix
    out[f"{p}candle_body_pct"] = _safe_div(body_abs, candle_range)
    out[f"{p}candle_body_atr"] = _safe_div(body_abs, atr)
    out[f"{p}candle_upper_wick_pct"] = _safe_div(upper_wick, candle_range)
    out[f"{p}candle_lower_wick_pct"] = _safe_div(lower_wick, candle_range)
    out[f"{p}candle_close_location"] = _safe_div(close - low, candle_range)
    out[f"{p}candle_direction"] = direction
    out[f"{p}candle_atr_ratio"] = _safe_div(candle_range, atr)
    out[f"{p}candle_range_ratio"] = _safe_div(candle_range, range_median)
    out[f"{p}candle_volume_ratio"] = _safe_div(volume, volume_median)
    out[f"{p}candle_inside_bar"] = ((high < prior_high) & (low > prior_low)).astype(int)
    out[f"{p}candle_outside_bar"] = ((high > prior_high) & (low < prior_low)).astype(int)
    out[f"{p}candle_bull_engulf"] = (
        (direction > 0)
        & (prior_close < prior_open)
        & (body_high >= prior_body_high)
        & (body_low <= prior_body_low)
    ).astype(int)
    out[f"{p}candle_bear_engulf"] = (
        (direction < 0)
        & (prior_close > prior_open)
        & (body_high >= prior_body_high)
        & (body_low <= prior_body_low)
    ).astype(int)
    out[f"{p}candle_breakout_up"] = (close > recent_high).astype(int)
    out[f"{p}candle_breakout_down"] = (close < recent_low).astype(int)
    out[f"{p}candle_ema_stack"] = (
        ((close > ema20) & (ema20 > ema50)).astype(int)
        - ((close < ema20) & (ema20 < ema50)).astype(int)
    )
    out[f"{p}candle_ema20_slope_pct"] = ema20.pct_change(3) * 100.0
    out[f"{p}candle_ema50_slope_pct"] = ema50.pct_change(6) * 100.0

    scored = out.apply(lambda row: score_candle_context_row(row, prefix=p), axis=1, result_type="expand")
    for column in scored.columns:
        out[column] = scored[column]
    return out.replace([float("inf"), float("-inf")], pd.NA)


def score_candle_context_row(row: pd.Series, *, prefix: str = "") -> dict[str, Any]:
    p = prefix
    long_score = 0.0
    short_score = 0.0
    reasons: list[str] = []

    direction = _num(row.get(f"{p}candle_direction"))
    body_pct = _num(row.get(f"{p}candle_body_pct"))
    body_atr = _num(row.get(f"{p}candle_body_atr"))
    upper_wick = _num(row.get(f"{p}candle_upper_wick_pct"))
    lower_wick = _num(row.get(f"{p}candle_lower_wick_pct"))
    close_location = _num(row.get(f"{p}candle_close_location"), 0.5)
    atr_ratio = _num(row.get(f"{p}candle_atr_ratio"), 1.0)
    range_ratio = _num(row.get(f"{p}candle_range_ratio"), 1.0)
    volume_ratio = _num(row.get(f"{p}candle_volume_ratio"), 1.0)
    ema_stack = _num(row.get(f"{p}candle_ema_stack"))
    ema20_slope = _num(row.get(f"{p}candle_ema20_slope_pct"))
    ema50_slope = _num(row.get(f"{p}candle_ema50_slope_pct"))

    if body_pct >= 0.45 and body_atr >= 0.35:
        if direction > 0 and close_location >= 0.65:
            long_score += 1.0
            reasons.append("body:bull_acceptance")
        elif direction < 0 and close_location <= 0.35:
            short_score += 1.0
            reasons.append("body:bear_acceptance")

    if lower_wick >= 0.45 and close_location >= 0.55:
        long_score += 0.9
        reasons.append("wick:lower_rejection")
    if upper_wick >= 0.45 and close_location <= 0.45:
        short_score += 0.9
        reasons.append("wick:upper_rejection")

    if _bool(row.get(f"{p}candle_bull_engulf")) and close_location >= 0.60:
        long_score += 0.8
        reasons.append("pattern:bull_engulf")
    if _bool(row.get(f"{p}candle_bear_engulf")) and close_location <= 0.40:
        short_score += 0.8
        reasons.append("pattern:bear_engulf")

    if _bool(row.get(f"{p}candle_breakout_up")) and close_location >= 0.65 and volume_ratio >= 1.05:
        long_score += 0.9
        reasons.append("structure:breakout_up")
    if _bool(row.get(f"{p}candle_breakout_down")) and close_location <= 0.35 and volume_ratio >= 1.05:
        short_score += 0.9
        reasons.append("structure:breakout_down")

    if ema_stack > 0 and ema20_slope >= 0 and ema50_slope >= -0.02:
        long_score += 0.6
        reasons.append("trend:ema_bull")
    elif ema_stack < 0 and ema20_slope <= 0 and ema50_slope <= 0.02:
        short_score += 0.6
        reasons.append("trend:ema_bear")

    if _bool(row.get(f"{p}candle_outside_bar")):
        if 0.40 <= close_location <= 0.60:
            reasons.append("bar:outside_mid")
        elif close_location > 0.65:
            long_score += 0.5
            reasons.append("bar:outside_high_close")
        elif close_location < 0.35:
            short_score += 0.5
            reasons.append("bar:outside_low_close")

    if _bool(row.get(f"{p}candle_inside_bar")) or range_ratio <= 0.70:
        reasons.append("bar:compression")

    if atr_ratio >= 1.8:
        reasons.append("vol:extreme_expansion")
    elif atr_ratio >= 1.2:
        reasons.append("vol:expansion")

    diff = long_score - short_score
    if diff >= 0.70:
        bias = 1
    elif diff <= -0.70:
        bias = -1
    else:
        bias = 0
    return {
        f"{p}candle_score_long": round(float(long_score), 4),
        f"{p}candle_score_short": round(float(short_score), 4),
        f"{p}candle_bias": int(bias),
        f"{p}candle_confidence": round(float(abs(diff)), 4),
        f"{p}candle_reasons": "|".join(reasons),
    }


def _state(row: pd.Series, prefix: str, label: str, weight: float) -> dict[str, Any]:
    return {
        "label": label,
        "prefix": prefix,
        "weight": float(weight),
        "bias": int(_num(row.get(f"{prefix}candle_bias"), 0.0)),
        "confidence": _num(row.get(f"{prefix}candle_confidence"), 0.0),
        "inside": _bool(row.get(f"{prefix}candle_inside_bar")),
        "outside": _bool(row.get(f"{prefix}candle_outside_bar")),
        "close_location": _num(row.get(f"{prefix}candle_close_location"), 0.5),
        "atr_ratio": _num(row.get(f"{prefix}candle_atr_ratio"), 1.0),
        "reasons": str(row.get(f"{prefix}candle_reasons", "") or ""),
    }


def _bias_name(value: float) -> str:
    if value > 0.20:
        return "long"
    if value < -0.20:
        return "short"
    return "neutral"


def multi_timeframe_candle_decision(
    row: pd.Series,
    *,
    side: str,
    weekly_prefix: str = "ctx_1w_",
    daily_prefix: str = "ctx_1d_",
    h4_prefix: str = "ctx_4h_",
    h1_prefix: str = "ctx_1h_",
    trigger_prefix: str = "base_",
) -> MultiTimeframeCandleDecision:
    side = str(side).lower()
    if side not in {"long", "short"}:
        return MultiTimeframeCandleDecision(1.0, False, "both_allowed", "neutral", 0.0, ("mtf:wait_side",))
    side_sign = 1 if side == "long" else -1
    states = [
        _state(row, weekly_prefix, "weekly", 1.6),
        _state(row, daily_prefix, "daily", 1.4),
        _state(row, h4_prefix, "4h", 1.1),
        _state(row, h1_prefix, "1h", 0.9),
        _state(row, trigger_prefix, "trigger", 0.5),
    ]
    context_states = [item for item in states[:4] if item["confidence"] > 0 or item["inside"] or item["outside"]]
    weighted = 0.0
    total_weight = 0.0
    for item in states:
        if item["bias"] == 0 or item["confidence"] <= 0:
            continue
        weight = item["weight"] * min(item["confidence"], 2.0)
        weighted += item["bias"] * weight
        total_weight += weight
    combined = weighted / total_weight if total_weight else 0.0
    confidence = min(abs(combined), 1.0)
    permission = {
        "long": "long_only",
        "short": "short_only",
        "neutral": "both_allowed",
    }[_bias_name(combined)]

    reasons: list[str] = []
    multiplier = 1.0
    block = False

    if not context_states:
        return MultiTimeframeCandleDecision(
            0.0,
            True,
            "no_trade",
            "neutral",
            0.0,
            ("mtf:no_higher_timeframe_context",),
        )

    weekly, daily, h4, h1, trigger = states
    if weekly["bias"] and daily["bias"] and weekly["bias"] != daily["bias"]:
        block = True
        reasons.append("mtf:weekly_daily_conflict")

    if weekly["inside"] and daily["inside"]:
        block = True
        reasons.append("mtf:weekly_daily_compression")
    elif weekly["inside"] or daily["inside"]:
        multiplier *= 0.70
        reasons.append("mtf:htf_inside_bar")

    for item in (weekly, daily):
        if item["outside"] and 0.40 <= item["close_location"] <= 0.60:
            block = True
            reasons.append(f"mtf:{item['label']}_outside_mid")

    if daily["atr_ratio"] >= 1.8 and daily["bias"] == side_sign:
        block = True
        reasons.append("mtf:daily_late_extreme_expansion")

    strong_conflicts = 0
    for item in states[:4]:
        if item["bias"] == 0 or item["confidence"] < 0.55:
            continue
        if item["bias"] == side_sign:
            boost = 1.0 + min(0.06 * item["weight"], 0.10)
            multiplier *= boost
            reasons.append(f"mtf:{item['label']}_aligned")
        else:
            strong_conflicts += 1
            multiplier *= 0.55 if item["label"] in {"weekly", "daily"} else 0.70
            reasons.append(f"mtf:{item['label']}_against")

    if h4["bias"] and h1["bias"] and h4["bias"] != h1["bias"]:
        multiplier *= 0.60
        reasons.append("mtf:4h_1h_conflict")

    if trigger["bias"] == side_sign and trigger["confidence"] >= 0.55:
        multiplier *= 1.04
        reasons.append("mtf:trigger_aligned")
    elif trigger["bias"] == -side_sign and trigger["confidence"] >= 0.55:
        multiplier *= 0.60
        reasons.append("mtf:trigger_against")

    if strong_conflicts >= 2:
        block = True
        reasons.append("mtf:multiple_contexts_against")

    if block:
        return MultiTimeframeCandleDecision(
            0.0,
            True,
            "no_trade",
            _bias_name(combined),
            round(float(confidence), 4),
            tuple(dict.fromkeys(reasons)),
        )

    multiplier = max(0.10, min(1.30, multiplier))
    return MultiTimeframeCandleDecision(
        round(float(multiplier), 4),
        False,
        permission,
        _bias_name(combined),
        round(float(confidence), 4),
        tuple(dict.fromkeys(reasons)) or ("mtf:neutral",),
    )
