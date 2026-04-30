from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

import config


PROFILE_COLUMNS = (
    "vp_poc",
    "vp_vah",
    "vp_val",
    "vp_width_pct",
    "vp_distance_to_poc_pct",
    "vp_position",
)


@dataclass(frozen=True)
class VolumeProfileDecision:
    multiplier: float
    block_new_entries: bool
    reasons: tuple[str, ...]


def add_volume_profile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a rolling volume profile using only bars before the current signal bar.

    This is intentionally conservative: volume is assigned to each historical
    bar's typical price. It is reproducible from Binance OHLCV and avoids any
    TradingView-only data dependency.
    """
    if not getattr(config, "VOLUME_PROFILE_ENABLED", False):
        return df

    out = df.copy()
    for col in PROFILE_COLUMNS:
        out[col] = np.nan
    out["vp_position"] = None

    lookback = int(getattr(config, "VOLUME_PROFILE_LOOKBACK", 120))
    min_bars = int(getattr(config, "VOLUME_PROFILE_MIN_BARS", max(30, lookback // 2)))
    bins = int(getattr(config, "VOLUME_PROFILE_BINS", 48))
    value_area_pct = float(getattr(config, "VOLUME_PROFILE_VALUE_AREA_PCT", 0.70))

    if lookback <= 0 or min_bars <= 0 or bins < 8:
        return out

    typical = (out["high"] + out["low"] + out["close"]) / 3.0
    volume = out["volume"].astype(float)

    for i in range(len(out)):
        start = max(0, i - lookback)
        if i - start < min_bars:
            continue

        window = out.iloc[start:i]
        price_low = float(window["low"].min())
        price_high = float(window["high"].max())
        if not math.isfinite(price_low) or not math.isfinite(price_high) or price_high <= price_low:
            continue

        prices = typical.iloc[start:i].to_numpy(dtype=float)
        vols = volume.iloc[start:i].to_numpy(dtype=float)
        valid = np.isfinite(prices) & np.isfinite(vols) & (vols > 0)
        if valid.sum() < min_bars:
            continue

        hist, edges = np.histogram(
            prices[valid],
            bins=bins,
            range=(price_low, price_high),
            weights=vols[valid],
        )
        total_volume = float(hist.sum())
        if total_volume <= 0:
            continue

        poc_idx = int(hist.argmax())
        left, right = _expand_value_area(hist, poc_idx, total_volume * value_area_pct)
        centers = (edges[:-1] + edges[1:]) / 2.0

        poc = float(centers[poc_idx])
        val = float(edges[left])
        vah = float(edges[right + 1])
        close = float(out["close"].iloc[i])
        if close <= 0 or not math.isfinite(close):
            continue

        if close > vah:
            position = "above_value"
        elif close < val:
            position = "below_value"
        else:
            position = "inside_value"

        out.iat[i, out.columns.get_loc("vp_poc")] = poc
        out.iat[i, out.columns.get_loc("vp_vah")] = vah
        out.iat[i, out.columns.get_loc("vp_val")] = val
        out.iat[i, out.columns.get_loc("vp_width_pct")] = (vah - val) / close
        out.iat[i, out.columns.get_loc("vp_distance_to_poc_pct")] = abs(close - poc) / close
        out.iat[i, out.columns.get_loc("vp_position")] = position

    return out


def _expand_value_area(hist: np.ndarray, poc_idx: int, target_volume: float) -> tuple[int, int]:
    left = right = poc_idx
    cumulative = float(hist[poc_idx])

    while cumulative < target_volume and (left > 0 or right < len(hist) - 1):
        left_vol = float(hist[left - 1]) if left > 0 else -1.0
        right_vol = float(hist[right + 1]) if right < len(hist) - 1 else -1.0

        if right_vol >= left_vol and right < len(hist) - 1:
            right += 1
            cumulative += float(hist[right])
        elif left > 0:
            left -= 1
            cumulative += float(hist[left])
        else:
            break

    return left, right


def profile_risk_decision(bar, side: str) -> VolumeProfileDecision:
    """Return a risk multiplier from rolling POC/VAH/VAL context."""
    if not getattr(config, "VOLUME_PROFILE_RISK_ENABLED", False):
        return VolumeProfileDecision(1.0, False, ())

    position = bar.get("vp_position")
    if not isinstance(position, str):
        return VolumeProfileDecision(1.0, False, ())

    mult = 1.0
    reasons: list[str] = []

    if side == "long":
        if position == "above_value":
            mult *= 1.05
            reasons.append("vp:long_above_value")
        elif position == "inside_value":
            mult *= 0.95
            reasons.append("vp:inside_value")
        elif position == "below_value":
            mult *= 0.85
            reasons.append("vp:long_below_value")
    elif side == "short":
        if position == "below_value":
            mult *= 1.05
            reasons.append("vp:short_below_value")
        elif position == "inside_value":
            mult *= 0.95
            reasons.append("vp:inside_value")
        elif position == "above_value":
            mult *= 0.85
            reasons.append("vp:short_above_value")

    near_poc_pct = _num(getattr(config, "VOLUME_PROFILE_NEAR_POC_PCT", 0.004))
    distance_to_poc = _num(bar.get("vp_distance_to_poc_pct"))
    if near_poc_pct is not None and distance_to_poc is not None and distance_to_poc <= near_poc_pct:
        mult *= 0.95
        reasons.append("vp:near_poc")

    width_pct = _num(bar.get("vp_width_pct"))
    narrow_pct = _num(getattr(config, "VOLUME_PROFILE_NARROW_VALUE_PCT", 0.018))
    if width_pct is not None and narrow_pct is not None and width_pct <= narrow_pct:
        mult *= 0.95
        reasons.append("vp:narrow_value")

    min_mult = float(getattr(config, "VOLUME_PROFILE_MIN_MULT", 0.80))
    max_mult = float(getattr(config, "VOLUME_PROFILE_MAX_MULT", 1.08))
    mult = max(min_mult, min(max_mult, mult))

    block = False
    if getattr(config, "VOLUME_PROFILE_BLOCK_CONTRA_VALUE", False):
        block = (side == "long" and position == "below_value") or (
            side == "short" and position == "above_value"
        )

    return VolumeProfileDecision(mult, block, tuple(reasons))


def _num(value, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default
