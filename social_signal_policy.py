from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from typing import Any, Iterable


DEFAULT_ALLOWLIST = ("BTC", "ETH", "BNB", "SOL", "DOGE", "LINK", "TRX", "XRP", "ADA", "AVAX")

PLATFORM_WEIGHTS = {
    "official": 1.0,
    "regulator": 1.0,
    "exchange": 0.9,
    "major_news": 0.8,
    "tradingview": 0.65,
    "x_verified_project": 0.7,
    "x_influencer": 0.45,
    "reddit": 0.45,
    "discord": 0.5,
    "telegram": 0.35,
    "youtube": 0.35,
    "coinmarketcap": 0.4,
    "coingecko": 0.45,
    "whatsapp_export": 0.3,
    "news_comments": 0.25,
}

SOURCE_TIER_WEIGHTS = {
    "official": 1.0,
    "verified": 0.8,
    "public": 0.55,
    "private_export": 0.45,
    "anonymous": 0.25,
}

LONG_TERMS = (
    "long",
    "buy",
    "bullish",
    "breakout",
    "reclaim",
    "support holds",
    "accumulation",
    "bounce",
    "higher high",
    "higher low",
    "uptrend",
    "al",
    "yukari",
    "destek",
    "kirildi",
)
SHORT_TERMS = (
    "short",
    "sell",
    "bearish",
    "breakdown",
    "reject",
    "resistance",
    "dump",
    "lower high",
    "lower low",
    "downtrend",
    "sat",
    "asagi",
    "direnc",
)
TECHNICAL_TERMS = (
    "support",
    "resistance",
    "trendline",
    "breakout",
    "breakdown",
    "retest",
    "vwap",
    "ema",
    "rsi",
    "macd",
    "fibonacci",
    "liquidity",
    "destek",
    "direnc",
)
NEWS_TERMS = (
    "fed",
    "fomc",
    "cpi",
    "nfp",
    "sec",
    "etf",
    "lawsuit",
    "hack",
    "listing",
    "delisting",
    "binance",
    "okx",
    "bybit",
)
RUMOR_TERMS = ("rumor", "unconfirmed", "leak", "insider", "soylenti")
SCAM_TERMS = (
    "guaranteed",
    "no risk",
    "risk free",
    "vip",
    "pump",
    "100x",
    "1000x",
    "x10",
    "send usdt",
    "private key",
    "seed phrase",
    "airdrop send",
    "giveaway send",
    "insider call",
    "exact time",
    "referral",
    "copy trade now",
)


@dataclass(frozen=True)
class SocialSignalDecision:
    symbols: tuple[str, ...]
    platform: str
    source_tier: str
    intent: str
    bias: str
    action: str
    can_open_trade: bool
    text_signal_score: float
    source_credibility: float
    freshness_score: float
    confirmation_score: float
    manipulation_risk_score: float
    final_score: float
    reasons: tuple[str, ...]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _norm_text(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _term_count(text: str, terms: Iterable[str]) -> int:
    return sum(1 for term in terms if term in text)


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def freshness_score(observed_at: Any = None, now: Any = None, *, half_life_seconds: int = 1800) -> float:
    observed = _parse_dt(observed_at)
    current = _parse_dt(now) or datetime.now(timezone.utc)
    if observed is None:
        return 0.65
    age = max(0.0, (current - observed).total_seconds())
    return round(_clamp(math.exp(-age / max(float(half_life_seconds), 1.0))), 4)


def extract_symbols(text: str, allowlist: Iterable[str] = DEFAULT_ALLOWLIST) -> tuple[str, ...]:
    allowed = {str(symbol).upper().replace("USDT", "") for symbol in allowlist}
    upper = str(text or "").upper()
    candidates: list[str] = []
    candidates.extend(match.upper() for match in re.findall(r"\$([A-Z]{2,10})\b", upper))
    candidates.extend(match.upper() for match in re.findall(r"\b([A-Z]{2,10})(?:/|-)?USDT\b", upper))
    for symbol in allowed:
        if re.search(rf"\b{re.escape(symbol)}\b", upper):
            candidates.append(symbol)

    out: list[str] = []
    for candidate in candidates:
        cleaned = candidate.replace("USDT", "")
        if cleaned in allowed and cleaned not in out:
            out.append(cleaned)
    return tuple(out)


def classify_social_text(
    text: str,
    *,
    platform: str,
    source_tier: str = "public",
    observed_at: Any = None,
    now: Any = None,
    author_reputation: float = 1.0,
    historical_precision: float = 1.0,
    price_confirmation_score: float = 0.0,
    independent_confirmation_score: float = 0.0,
    source_diversity_score: float = 0.0,
    copy_paste_ratio: float = 0.0,
    platform_concentration_score: float = 0.0,
    is_late_after_move: bool = False,
    allowlist: Iterable[str] = DEFAULT_ALLOWLIST,
) -> SocialSignalDecision:
    """Classify one social/news text as context, never as direct trade authority."""
    normalized = _norm_text(text)
    platform_key = str(platform or "").strip().lower()
    source_key = str(source_tier or "public").strip().lower()
    symbols = extract_symbols(text, allowlist)
    reasons: list[str] = []

    long_hits = _term_count(normalized, LONG_TERMS)
    short_hits = _term_count(normalized, SHORT_TERMS)
    technical_hits = _term_count(normalized, TECHNICAL_TERMS)
    news_hits = _term_count(normalized, NEWS_TERMS)
    rumor_hits = _term_count(normalized, RUMOR_TERMS)
    scam_hits = _term_count(normalized, SCAM_TERMS)

    if scam_hits:
        intent = "pump_invitation" if "pump" in normalized or "100x" in normalized else "scam"
    elif rumor_hits:
        intent = "rumor"
    elif news_hits and not technical_hits:
        intent = "news"
    elif technical_hits:
        intent = "technical_analysis"
    elif long_hits or short_hits:
        intent = "trade_signal"
    else:
        intent = "unknown"

    if long_hits > short_hits:
        bias = "long"
    elif short_hits > long_hits:
        bias = "short"
    else:
        bias = "wait"

    if not symbols:
        reasons.append("social:no_allowlisted_symbol")
    if bias != "wait":
        reasons.append(f"social:text_bias_{bias}")
    if technical_hits:
        reasons.append("social:technical_context")
    if news_hits:
        reasons.append("social:news_context")
    if rumor_hits:
        reasons.append("social:rumor")
    if scam_hits:
        reasons.append("social:pump_or_scam_language")

    platform_weight = PLATFORM_WEIGHTS.get(platform_key, 0.3)
    source_weight = SOURCE_TIER_WEIGHTS.get(source_key, 0.45)
    source_credibility = _clamp(
        platform_weight * 0.45
        + source_weight * 0.35
        + _clamp(_num(author_reputation, 1.0)) * 0.10
        + _clamp(_num(historical_precision, 1.0)) * 0.10
    )

    directional_hits = abs(long_hits - short_hits)
    total_directional = max(long_hits + short_hits, 1)
    text_signal_score = 0.0
    if bias != "wait":
        text_signal_score = 0.2 + min(directional_hits / max(total_directional, 1), 1.0) * 0.35
        text_signal_score += min(technical_hits, 3) * 0.07
        text_signal_score += min(news_hits, 2) * 0.05
    text_signal_score = _clamp(text_signal_score)

    fresh = freshness_score(observed_at, now)
    confirmation = _clamp(
        _clamp(_num(price_confirmation_score)) * 0.45
        + _clamp(_num(independent_confirmation_score)) * 0.35
        + _clamp(_num(source_diversity_score)) * 0.20
    )

    manipulation = 0.0
    manipulation += min(scam_hits, 3) * 0.23
    manipulation += min(rumor_hits, 2) * 0.12
    manipulation += _clamp(_num(copy_paste_ratio)) * 0.25
    manipulation += _clamp(_num(platform_concentration_score)) * 0.20
    if is_late_after_move:
        manipulation += 0.20
        reasons.append("social:late_after_move")
    if source_key in {"anonymous", "private_export"} and platform_key in {"telegram", "whatsapp_export", "discord"}:
        manipulation += 0.10
    manipulation = _clamp(manipulation)

    final_score = _clamp(
        text_signal_score * 0.35
        + source_credibility * 0.25
        + fresh * 0.15
        + confirmation * 0.25
        - manipulation * 0.50
    )

    if manipulation >= 0.70 or intent in {"scam", "pump_invitation"}:
        action = "block"
        reasons.append("social:block_manipulation_risk")
    elif (
        bias in {"long", "short"}
        and symbols
        and final_score >= 0.62
        and _num(price_confirmation_score) >= 0.55
        and _num(independent_confirmation_score) >= 0.50
        and manipulation < 0.35
    ):
        action = f"paper_{bias}"
        reasons.append("social:paper_context_only")
    elif bias in {"long", "short"} and symbols and final_score >= 0.35:
        action = "alert_only"
        reasons.append("social:needs_price_confirmation")
    else:
        action = "observe"

    return SocialSignalDecision(
        symbols=symbols,
        platform=platform_key,
        source_tier=source_key,
        intent=intent,
        bias=bias,
        action=action,
        can_open_trade=False,
        text_signal_score=round(float(text_signal_score), 4),
        source_credibility=round(float(source_credibility), 4),
        freshness_score=round(float(fresh), 4),
        confirmation_score=round(float(confirmation), 4),
        manipulation_risk_score=round(float(manipulation), 4),
        final_score=round(float(final_score), 4),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def aggregate_social_signals(
    signals: Iterable[SocialSignalDecision],
    *,
    symbol: str,
    price_action_bias: str = "wait",
) -> dict[str, Any]:
    """Aggregate already-scored messages for a symbol into a cached bot context."""
    wanted = str(symbol).upper().replace("USDT", "")
    rows = [signal for signal in signals if wanted in signal.symbols]
    if not rows:
        return {
            "symbol": wanted,
            "bias": "wait",
            "action": "observe",
            "can_open_trade": False,
            "score": 0.0,
            "manipulation_risk_score": 0.0,
            "reasons": ("social:no_messages",),
        }

    long_score = 0.0
    short_score = 0.0
    reasons: list[str] = []
    manipulation = 0.0
    for row in rows:
        weight = max(row.final_score, 0.0) * max(row.source_credibility, 0.1)
        if row.bias == "long":
            long_score += weight
        elif row.bias == "short":
            short_score += weight
        manipulation = max(manipulation, row.manipulation_risk_score)
        reasons.extend(row.reasons)

    if manipulation >= 0.70:
        return {
            "symbol": wanted,
            "bias": "wait",
            "action": "block",
            "can_open_trade": False,
            "score": round(max(long_score, short_score), 4),
            "manipulation_risk_score": round(manipulation, 4),
            "reasons": tuple(dict.fromkeys(reasons + ["social:aggregate_block"])),
        }

    diff = long_score - short_score
    if diff > 0.15:
        bias = "long"
    elif diff < -0.15:
        bias = "short"
    else:
        bias = "wait"

    action = "observe"
    if bias in {"long", "short"}:
        action = "alert_only"
        if price_action_bias == bias:
            action = f"paper_{bias}"
            reasons.append("social:aggregate_price_confirmed")

    return {
        "symbol": wanted,
        "bias": bias,
        "action": action,
        "can_open_trade": False,
        "score": round(max(long_score, short_score), 4),
        "manipulation_risk_score": round(manipulation, 4),
        "reasons": tuple(dict.fromkeys(reasons)),
    }
