from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class BtcLeaderDecision:
    multiplier: float
    block_new_entries: bool
    bias: str
    confidence: float
    reasons: tuple[str, ...]


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    return num / den.replace(0, pd.NA)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if pd.notna(out) else default


def add_btc_leader_features(
    symbol_df: pd.DataFrame,
    btc_df: pd.DataFrame,
    *,
    lookback: int = 96,
    prefix: str = "btc_",
) -> pd.DataFrame:
    """Add BTC market-leader context to a symbol OHLCV frame without lookahead."""
    out = symbol_df.copy()
    btc = btc_df[["open", "high", "low", "close", "volume"]].copy().sort_index()
    btc = btc.reindex(out.index, method="ffill")

    sym_close = pd.to_numeric(out["close"], errors="coerce")
    btc_close = pd.to_numeric(btc["close"], errors="coerce")
    sym_ret = sym_close.pct_change()
    btc_ret = btc_close.pct_change()
    lookback = max(10, int(lookback))

    btc_ema_fast = btc_close.ewm(span=20, adjust=False).mean()
    btc_ema_slow = btc_close.ewm(span=80, adjust=False).mean()
    btc_trend_strength = _safe_div(btc_ema_fast - btc_ema_slow, btc_close) * 100.0
    btc_realized_vol = btc_ret.rolling(lookback, min_periods=max(10, lookback // 4)).std() * 100.0
    btc_ret_z = btc_ret / btc_ret.rolling(lookback, min_periods=max(10, lookback // 4)).std().replace(0, pd.NA)
    rolling_corr = sym_ret.rolling(lookback, min_periods=max(10, lookback // 4)).corr(btc_ret)
    rolling_cov = sym_ret.rolling(lookback, min_periods=max(10, lookback // 4)).cov(btc_ret)
    rolling_var = btc_ret.rolling(lookback, min_periods=max(10, lookback // 4)).var()
    beta = rolling_cov / rolling_var.replace(0, pd.NA)
    residual_ret = sym_ret - beta * btc_ret
    relative_strength = sym_close.pct_change(12) - btc_close.pct_change(12)

    out[f"{prefix}ret_1"] = btc_ret * 100.0
    out[f"{prefix}ret_3"] = btc_close.pct_change(3) * 100.0
    out[f"{prefix}ret_12"] = btc_close.pct_change(12) * 100.0
    out[f"{prefix}trend_strength"] = btc_trend_strength
    out[f"{prefix}trend_slope"] = btc_trend_strength.diff(3)
    out[f"{prefix}realized_vol_pct"] = btc_realized_vol
    out[f"{prefix}shock_z"] = btc_ret_z
    out[f"{prefix}corr"] = rolling_corr
    out[f"{prefix}beta"] = beta
    out[f"{prefix}residual_ret"] = residual_ret * 100.0
    out[f"{prefix}relative_strength_12"] = relative_strength * 100.0
    return out.replace([float("inf"), float("-inf")], pd.NA)


def btc_leader_decision(row: pd.Series, *, side: str) -> BtcLeaderDecision:
    """Soft BTC permission layer for altcoin long/short decisions."""
    side = str(side).lower().strip()
    if side not in {"long", "short"}:
        return BtcLeaderDecision(1.0, False, "neutral", 0.0, ("btc:invalid_side",))

    btc_ret = _num(row.get("btc_ret_3"))
    btc_trend = _num(row.get("btc_trend_strength"))
    btc_slope = _num(row.get("btc_trend_slope"))
    btc_shock = _num(row.get("btc_shock_z"))
    corr = _num(row.get("btc_corr"))
    beta = _num(row.get("btc_beta"))
    rel = _num(row.get("btc_relative_strength_12"))

    btc_direction_score = btc_ret * 0.45 + btc_trend * 0.35 + btc_slope * 0.20
    if btc_direction_score > 0.02:
        btc_bias = "bullish"
    elif btc_direction_score < -0.02:
        btc_bias = "bearish"
    else:
        btc_bias = "neutral"

    desired = 1 if side == "long" else -1
    btc_signed = 1 if btc_bias == "bullish" else (-1 if btc_bias == "bearish" else 0)
    connected = abs(corr) >= 0.45 and beta > 0.20
    shock_against = abs(btc_shock) >= 2.0 and btc_signed == -desired and connected
    shock_with = abs(btc_shock) >= 2.0 and btc_signed == desired and connected

    multiplier = 1.0
    block = False
    reasons: list[str] = []

    if connected and btc_signed == desired:
        multiplier *= 1.08
        reasons.append("btc:aligned")
    elif connected and btc_signed == -desired:
        multiplier *= 0.55
        reasons.append("btc:against")
    elif not connected:
        multiplier *= 0.90
        reasons.append("btc:decoupled")
    else:
        multiplier *= 0.95
        reasons.append("btc:neutral")

    if shock_against:
        block = True
        multiplier = 0.0
        reasons.append("btc:shock_against")
    elif shock_with:
        multiplier *= 0.85
        reasons.append("btc:shock_with_reduce_chase")

    if side == "long" and rel < -1.0 and connected:
        multiplier *= 0.85
        reasons.append("btc:alt_underperforming")
    elif side == "short" and rel > 1.0 and connected:
        multiplier *= 0.85
        reasons.append("btc:alt_outperforming")

    confidence = min(1.0, max(0.0, abs(corr) * min(max(beta, 0.0), 2.0) / 2.0))
    return BtcLeaderDecision(round(multiplier, 4), block, btc_bias, round(confidence, 4), tuple(reasons))
