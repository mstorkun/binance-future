"""
News/event impact scoring.

This module intentionally avoids trading directly from headlines. It converts a
normalized news item into a conservative risk decision that a future
`news_watcher.py` can write into event_calendar.csv.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import pandas as pd


OFFICIAL_DOMAINS = {
    "binance.com",
    "federalreserve.gov",
    "bls.gov",
    "bea.gov",
    "sec.gov",
    "cftc.gov",
    "cmegroup.com",
}

TIER1_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "cnbc.com",
    "coindesk.com",
}


@dataclass(frozen=True)
class NewsItem:
    timestamp_utc: str
    title: str
    source: str = ""
    url: str = ""
    category: str = ""
    symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class NewsImpactDecision:
    direction: str
    impact: str
    risk_mult: float
    block_new_entries: bool
    post_minutes: int
    scope: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class MarketReaction:
    direction: str
    strength: float
    price_change_pct: float
    volume_ratio: float
    range_atr: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TradeBiasDecision:
    side: str | None
    confidence: float
    reasons: tuple[str, ...]


def source_reliability(item: NewsItem) -> float:
    domain = _domain(item.url) or item.source.lower().strip()
    if any(domain.endswith(d) for d in OFFICIAL_DOMAINS):
        return 1.0
    if any(domain.endswith(d) for d in TIER1_DOMAINS):
        return 0.85
    return 0.45


def assess_news_impact(item: NewsItem) -> NewsImpactDecision:
    text = f"{item.category} {item.title}".lower()
    reliability = source_reliability(item)
    reasons = [f"source:{reliability:.2f}"]

    direction = "uncertain"
    impact = "low"
    risk_mult = 1.0
    block = False
    post_minutes = 0
    scope = "market" if not item.symbols else "symbol"

    if _has_any(text, "tariff", "sanction", "war", "airstrike", "geopolitical", "trade war"):
        direction, impact = "bearish", "high"
        risk_mult, block, post_minutes = 0.20, True, 720
        reasons.append("shock:macro_geopolitical")
    elif _has_any(text, "fomc", "fed", "powell", "cpi", "inflation", "payrolls", "nfp", "pce"):
        direction, impact = "uncertain", "high"
        risk_mult, block, post_minutes = 0.35, True, 240
        reasons.append("scheduled_or_macro")
        if _has_any(text, "dovish", "rate cut", "cuts", "lower rates"):
            direction = "bullish"
            block = False
            risk_mult = 0.75
            reasons.append("macro:dovish")
        elif _has_any(text, "hawkish", "higher for longer", "hot inflation", "rate hike"):
            direction = "bearish"
            reasons.append("macro:hawkish")
    elif _has_any(text, "hack", "exploit", "breach", "outage", "withdrawal suspended", "trading suspended"):
        direction, impact = "bearish", "high"
        risk_mult, block, post_minutes = 0.25, True, 1440
        reasons.append("incident:exchange_or_protocol")
    elif _has_any(text, "delist", "suspend trading", "trading suspension"):
        direction, impact = "bearish", "high"
        risk_mult, block, post_minutes = 0.20, True, 1440
        scope = "symbol"
        reasons.append("incident:listing_status")
    elif _has_any(text, "etf inflow", "record inflow", "spot etf", "crypto week", "genius act", "clarity act"):
        direction, impact = "bullish", "medium"
        risk_mult, block, post_minutes = 1.10, False, 1440
        reasons.append("regime:institutional_or_policy")
    elif _has_any(text, "liquidation", "liquidations", "open interest", "funding"):
        direction, impact = "uncertain", "medium"
        risk_mult, block, post_minutes = 0.50, False, 240
        reasons.append("market_structure:forced_flow")

    if reliability < 0.70:
        risk_mult = min(risk_mult, 0.75)
        block = False if impact != "high" else block
        reasons.append("unconfirmed")

    return NewsImpactDecision(
        direction=direction,
        impact=impact,
        risk_mult=risk_mult,
        block_new_entries=block,
        post_minutes=post_minutes,
        scope=scope,
        reasons=tuple(reasons),
    )


def measure_market_reaction(
    df: pd.DataFrame,
    event_ts,
    reaction_minutes: int = 60,
    lookback_bars: int = 20,
) -> MarketReaction:
    """
    Measure actual post-news market reaction using only bars after publication.

    Expected columns: open/high/low/close/volume. If `atr` exists, it is used
    for range normalization; otherwise recent high-low range is used.
    """
    ts = pd.Timestamp(event_ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)

    market = df.sort_index()
    pre = market.loc[market.index < ts].tail(lookback_bars)
    post = market.loc[(market.index >= ts) & (market.index <= ts + pd.Timedelta(minutes=reaction_minutes))]
    if pre.empty or post.empty:
        return MarketReaction("neutral", 0.0, 0.0, 1.0, 0.0, ("reaction:insufficient_data",))

    pre_close = float(pre["close"].iloc[-1])
    post_close = float(post["close"].iloc[-1])
    if pre_close <= 0:
        return MarketReaction("neutral", 0.0, 0.0, 1.0, 0.0, ("reaction:bad_price",))

    price_change_pct = (post_close - pre_close) / pre_close
    pre_volume = float(pre["volume"].mean()) if "volume" in pre else 0.0
    post_volume = float(post["volume"].mean()) if "volume" in post else 0.0
    volume_ratio = post_volume / pre_volume if pre_volume > 0 else 1.0

    if "atr" in pre and float(pre["atr"].dropna().mean() or 0) > 0:
        normal_range = float(pre["atr"].dropna().mean())
    else:
        normal_range = float((pre["high"] - pre["low"]).dropna().mean() or 0)
    reaction_range = float(post["high"].max() - post["low"].min())
    range_atr = reaction_range / normal_range if normal_range > 0 else 0.0

    price_score = min(abs(price_change_pct) / 0.015, 1.0)
    volume_score = min(max((volume_ratio - 1.0) / 2.0, 0.0), 1.0)
    range_score = min(range_atr / 2.0, 1.0)
    strength = round(0.50 * price_score + 0.25 * volume_score + 0.25 * range_score, 3)

    if price_change_pct >= 0.005:
        direction = "bullish"
    elif price_change_pct <= -0.005:
        direction = "bearish"
    else:
        direction = "neutral"

    reasons = [
        f"reaction:price={price_change_pct * 100:.2f}%",
        f"reaction:volume={volume_ratio:.2f}x",
        f"reaction:range={range_atr:.2f}atr",
    ]
    return MarketReaction(direction, strength, price_change_pct, volume_ratio, range_atr, tuple(reasons))


def trade_bias_from_news_and_reaction(
    impact: NewsImpactDecision,
    reaction: MarketReaction,
) -> TradeBiasDecision:
    """
    Convert news plus confirmed market reaction into a conservative trade bias.

    Returns side=None unless both layers agree strongly enough.
    """
    reasons = list(impact.reasons + reaction.reasons)
    if impact.impact == "low" or reaction.strength < 0.45:
        reasons.append("bias:no_trade_weak_confirmation")
        return TradeBiasDecision(None, reaction.strength, tuple(reasons))
    if reaction.direction == "neutral" or impact.direction == "uncertain":
        reasons.append("bias:no_trade_uncertain_direction")
        return TradeBiasDecision(None, reaction.strength, tuple(reasons))
    if impact.direction != reaction.direction:
        reasons.append("bias:no_trade_news_reaction_conflict")
        return TradeBiasDecision(None, reaction.strength, tuple(reasons))

    side = "long" if reaction.direction == "bullish" else "short"
    confidence = min(1.0, reaction.strength * source_reliability_from_reasons(impact.reasons))
    reasons.append(f"bias:{side}")
    return TradeBiasDecision(side, round(confidence, 3), tuple(reasons))


def to_event_calendar_row(item: NewsItem, decision: NewsImpactDecision) -> dict:
    timestamp = pd.Timestamp(item.timestamp_utc)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return {
        "timestamp_utc": timestamp.isoformat(sep=" "),
        "event": item.title,
        "impact": decision.impact,
        "pre_minutes": 0,
        "post_minutes": decision.post_minutes,
        "risk_mult": decision.risk_mult,
        "block_new_entries": str(decision.block_new_entries).lower(),
    }


def _domain(url: str) -> str:
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _has_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def source_reliability_from_reasons(reasons: tuple[str, ...]) -> float:
    for reason in reasons:
        if reason.startswith("source:"):
            try:
                return float(reason.split(":", 1)[1])
            except ValueError:
                return 0.45
    return 0.45
