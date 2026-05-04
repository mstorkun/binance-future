from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


OFFICIAL_DOMAINS = {
    "federalreserve.gov",
    "bls.gov",
    "bea.gov",
    "sec.gov",
    "cftc.gov",
    "treasury.gov",
    "binance.com",
    "developers.binance.com",
    "cmegroup.com",
}

TIER1_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "cnbc.com",
    "coindesk.com",
}


@dataclass(frozen=True)
class NewsDirectionDecision:
    source_tier: str
    source_score: float
    content_bias: str
    content_score: float
    required_confirmation: str
    trade_bias: str
    action: str
    risk_mult: float
    reasons: tuple[str, ...]


def source_score(url: str = "", source: str = "") -> tuple[str, float]:
    domain = _domain(url) or str(source).lower().strip()
    if any(domain.endswith(item) for item in OFFICIAL_DOMAINS):
        return "official", 1.0
    if any(domain.endswith(item) for item in TIER1_DOMAINS):
        return "tier1", 0.85
    return "unconfirmed", 0.35


def content_bias(title: str, *, category: str = "", actual: float | None = None, forecast: float | None = None) -> tuple[str, float, tuple[str, ...]]:
    text = f"{category} {title}".lower()
    reasons: list[str] = []

    if actual is not None and forecast is not None:
        surprise = float(actual) - float(forecast)
        if _has_any(text, "cpi", "ppi", "pce", "inflation"):
            if surprise > 0:
                return "bearish", min(abs(surprise), 1.0), ("surprise:hot_inflation",)
            if surprise < 0:
                return "bullish", min(abs(surprise), 1.0), ("surprise:cold_inflation",)
        if _has_any(text, "payroll", "employment", "unemployment", "nfp"):
            if surprise > 0:
                return "mixed", min(abs(surprise), 1.0), ("surprise:strong_labor",)
            if surprise < 0:
                return "mixed", min(abs(surprise), 1.0), ("surprise:weak_labor",)

    if _has_any(text, "rate cut", "dovish", "easing", "lower inflation", "approval", "etf inflow", "record inflow"):
        reasons.append("text:risk_on")
        return "bullish", 0.70, tuple(reasons)
    if _has_any(text, "rate hike", "hawkish", "higher for longer", "hot inflation", "enforcement", "lawsuit", "outflow"):
        reasons.append("text:risk_off")
        return "bearish", 0.70, tuple(reasons)
    if _has_any(text, "delist", "trading suspension", "withdrawals suspended", "outage", "hack", "exploit", "depeg"):
        reasons.append("text:incident")
        return "bearish", 0.90, tuple(reasons)
    if _has_any(text, "listing", "will list", "launchpool"):
        reasons.append("text:listing")
        return "mixed", 0.65, tuple(reasons)
    if _has_any(text, "token unlock", "unlock"):
        reasons.append("text:supply_unlock")
        return "bearish", 0.60, tuple(reasons)
    return "uncertain", 0.0, ("text:uncertain",)


def decide_news_direction(
    *,
    title: str,
    url: str = "",
    source: str = "",
    category: str = "",
    actual: float | None = None,
    forecast: float | None = None,
    market_reaction: str = "unknown",
    market_reaction_score: float = 0.0,
) -> NewsDirectionDecision:
    tier, reliability = source_score(url, source)
    bias, score, reasons = content_bias(title, category=category, actual=actual, forecast=forecast)
    all_reasons = [f"source:{tier}", *reasons]

    if tier == "unconfirmed":
        return NewsDirectionDecision(tier, reliability, bias, score, "official_or_tier1_confirmation", "wait", "observe_only", 0.50, tuple(all_reasons + ["decision:unconfirmed_source"]))

    if bias in {"uncertain", "mixed"}:
        return NewsDirectionDecision(tier, reliability, bias, score, "market_reaction_required", "wait", "observe_only", 0.50, tuple(all_reasons + ["decision:uncertain_content"]))

    required_score = 0.45 if tier == "official" else 0.60
    if market_reaction_score < required_score:
        return NewsDirectionDecision(tier, reliability, bias, score, "price_volume_depth_confirmation", "wait", "observe_only", 0.50, tuple(all_reasons + ["decision:await_market_confirmation"]))

    if market_reaction not in {bias, "aligned"}:
        return NewsDirectionDecision(tier, reliability, bias, score, "conflict_resolution", "wait", "block_new_entries", 0.0, tuple(all_reasons + ["decision:news_market_conflict"]))

    trade_bias = "long" if bias == "bullish" else "short"
    return NewsDirectionDecision(tier, reliability, bias, score, "confirmed", trade_bias, "directional_allowed", 0.75 if tier == "tier1" else 1.0, tuple(all_reasons + [f"decision:{trade_bias}"]))


def _domain(url: str) -> str:
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _has_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)
