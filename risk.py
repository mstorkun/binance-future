import math
from dataclasses import dataclass

import calendar_risk
import config
import volume_profile as vp


def _num(value, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def position_size(balance: float, atr: float, price: float, risk_pct: float | None = None) -> float:
    """
    Risk tutarı (USDT) = bakiye × risk_pct
    Stop mesafesi (USDT/BTC) = ATR × çarpan
    Kontrat (BTC) = risk_usdt / stop_dist
    Kaldıraç margin'i etkiler, kontrat sayısını değil.
    """
    risk_pct = config.RISK_PER_TRADE_PCT if risk_pct is None else risk_pct
    risk_usdt = balance * risk_pct
    stop_dist = atr * config.SL_ATR_MULT
    contracts = risk_usdt / stop_dist
    return round(contracts, 4)


def correlation_aware_risk(open_count: int, base_risk: float) -> float:
    """Reduce new-entry risk as correlated portfolio exposure increases."""
    if not getattr(config, "CORRELATION_AWARE_SIZING_ENABLED", True):
        return base_risk
    if open_count <= 0:
        return base_risk
    if open_count == 1:
        return base_risk * 0.67
    if open_count == 2:
        return base_risk * 0.50
    return base_risk * 0.33


@dataclass(frozen=True)
class RiskDecision:
    multiplier: float
    block_new_entries: bool
    reasons: tuple[str, ...]


def _market_risk_assessment(bar, side: str) -> RiskDecision:
    """
    Market-state risk multiplier.

    Uses only already-closed signal-bar indicators. The goal is asymmetric:
    reduce size in weak/noisy regimes, and increase size only modestly when
    trend quality, daily trend, and volume pressure agree.
    """
    if not getattr(config, "DYNAMIC_RISK_ENABLED", False):
        return RiskDecision(1.0, False, ())

    mult = 1.0
    reasons: list[str] = []
    regime = bar.get("regime")
    adx = _num(bar.get("adx"))
    atr = _num(bar.get("atr"))
    close = _num(bar.get("close"))
    rsi = _num(bar.get("rsi"))
    daily_trend = _num(bar.get("daily_trend"))
    obv = _num(bar.get("obv"))
    obv_ema = _num(bar.get("obv_ema"))

    if regime == "trend":
        mult *= 1.10
        reasons.append("market:trend")
    elif regime == "range":
        mult *= 0.65
        reasons.append("market:range")

    if adx is not None:
        if adx >= 30:
            mult *= 1.10
            reasons.append("adx:strong")
        elif adx >= 25:
            mult *= 1.05
            reasons.append("adx:trend")
        elif adx < 15:
            mult *= 0.60
            reasons.append("adx:very_weak")
        elif adx < 18:
            mult *= 0.75
            reasons.append("adx:weak")

    if daily_trend in (1.0, -1.0):
        aligned = (side == "long" and daily_trend == 1.0) or (side == "short" and daily_trend == -1.0)
        mult *= 1.08 if aligned else 0.60
        reasons.append("daily:aligned" if aligned else "daily:against")

    if obv is not None and obv_ema is not None:
        obv_aligned = (side == "long" and obv > obv_ema) or (side == "short" and obv < obv_ema)
        mult *= 1.05 if obv_aligned else 0.90
        reasons.append("obv:aligned" if obv_aligned else "obv:against")

    if atr is not None and close and close > 0:
        atr_pct = atr / close
        if atr_pct >= 0.06:
            mult *= 0.55
            reasons.append("vol:extreme")
        elif atr_pct >= 0.04:
            mult *= 0.75
            reasons.append("vol:high")
        elif atr_pct >= 0.03:
            mult *= 0.90
            reasons.append("vol:elevated")

    if rsi is not None:
        if side == "long" and rsi >= 72:
            mult *= 0.85
            reasons.append("rsi:hot_long")
        elif side == "short" and rsi <= 28:
            mult *= 0.85
            reasons.append("rsi:cold_short")

    profile = vp.profile_risk_decision(bar, side)
    if profile.block_new_entries:
        return RiskDecision(0.0, True, tuple(reasons) + profile.reasons)
    mult *= profile.multiplier
    reasons.extend(profile.reasons)

    min_mult = getattr(config, "DYNAMIC_RISK_MIN_MULT", 0.5)
    max_mult = getattr(config, "DYNAMIC_RISK_MAX_MULT", 1.25)
    return RiskDecision(max(min_mult, min(max_mult, mult)), False, tuple(reasons))


def market_risk_multiplier(bar, side: str) -> float:
    return _market_risk_assessment(bar, side).multiplier


def entry_risk_decision(bar, side: str, ts=None) -> RiskDecision:
    """Combine market-state and calendar/news-event controls for new entries."""
    market = _market_risk_assessment(bar, side)
    cal = calendar_risk.calendar_risk_decision(ts if ts is not None else getattr(bar, "name", None))

    if cal.block_new_entries:
        return RiskDecision(0.0, True, market.reasons + cal.reasons)

    mult = market.multiplier * cal.multiplier
    min_mult = getattr(config, "FINAL_RISK_MIN_MULT", 0.10)
    max_mult = getattr(config, "FINAL_RISK_MAX_MULT", 1.25)
    mult = max(min_mult, min(max_mult, mult))
    return RiskDecision(mult, False, market.reasons + cal.reasons)


def sl_tp_prices(entry: float, atr: float, side: str) -> tuple[float, float]:
    stop_dist = atr * config.SL_ATR_MULT
    tp_dist   = atr * config.TP_ATR_MULT

    if side == "long":
        sl = entry - stop_dist
        tp = entry + tp_dist
    else:
        sl = entry + stop_dist
        tp = entry - tp_dist

    return round(sl, 2), round(tp, 2)


def daily_loss_exceeded(start_balance: float, current_balance: float) -> bool:
    loss_pct = (start_balance - current_balance) / start_balance
    return loss_pct >= config.DAILY_LOSS_LIMIT_PCT
