"""
Passive dynamic pair universe scoring.

This is a Freqtrade-style pairlist/filter helper for research and paper
diagnostics. It does not change config.SYMBOLS unless a caller explicitly uses
the returned list.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

import config


@dataclass(frozen=True)
class PairScore:
    symbol: str
    tradable: bool
    score: float
    reasons: tuple[str, ...]
    bars: int
    avg_quote_volume: float
    atr_pct: float | None
    funding_abs: float | None


def _num(value, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(out):
        return default
    return out


def _avg_quote_volume(df: pd.DataFrame, lookback: int = 120) -> float:
    if df.empty or "volume" not in df or "close" not in df:
        return 0.0
    window = df.tail(max(1, lookback))
    return float((window["volume"] * window["close"]).mean())


def _atr_pct(df: pd.DataFrame) -> float | None:
    if df.empty or "atr" not in df or "close" not in df:
        return None
    atr = _num(df["atr"].dropna().iloc[-1] if not df["atr"].dropna().empty else None)
    close = _num(df["close"].dropna().iloc[-1] if not df["close"].dropna().empty else None)
    if atr is None or close is None or close <= 0:
        return None
    return atr / close


def _funding_abs(funding: pd.DataFrame | None) -> float | None:
    if funding is None or funding.empty or "funding_rate" not in funding:
        return None
    recent = funding["funding_rate"].dropna().tail(21)
    if recent.empty:
        return None
    return float(recent.abs().mean())


def score_pair(symbol: str, data: dict) -> PairScore:
    df = data.get("df")
    if df is None:
        df = pd.DataFrame()
    funding = data.get("funding")

    bars = len(df)
    avg_quote_volume = _avg_quote_volume(df)
    atr_pct = _atr_pct(df)
    funding_abs = _funding_abs(funding)

    reasons: list[str] = []
    score = 0.0

    if bars < int(getattr(config, "PAIR_UNIVERSE_MIN_BARS", 1000)):
        reasons.append("pair:too_few_bars")
    else:
        score += 1.0

    if avg_quote_volume < float(getattr(config, "PAIR_UNIVERSE_MIN_AVG_QUOTE_VOLUME", 5_000_000.0)):
        reasons.append("pair:low_quote_volume")
    else:
        score += 1.0

    min_atr = float(getattr(config, "PAIR_UNIVERSE_MIN_ATR_PCT", 0.003))
    max_atr = float(getattr(config, "PAIR_UNIVERSE_MAX_ATR_PCT", 0.08))
    if atr_pct is None:
        reasons.append("pair:no_atr")
    elif atr_pct < min_atr:
        reasons.append("pair:too_quiet")
    elif atr_pct > max_atr:
        reasons.append("pair:too_volatile")
    else:
        score += 1.0

    max_funding = float(getattr(config, "PAIR_UNIVERSE_MAX_FUNDING_ABS", 0.0015))
    if funding_abs is not None and funding_abs > max_funding:
        reasons.append("pair:funding_expensive")
    else:
        score += 0.5

    tradable = not reasons and score >= float(getattr(config, "PAIR_UNIVERSE_MIN_SCORE", 0.0))
    return PairScore(
        symbol=symbol,
        tradable=tradable,
        score=round(score, 4),
        reasons=tuple(reasons),
        bars=bars,
        avg_quote_volume=round(avg_quote_volume, 4),
        atr_pct=round(atr_pct, 8) if atr_pct is not None else None,
        funding_abs=round(funding_abs, 8) if funding_abs is not None else None,
    )


def score_universe(symbols: list[str], data_by_symbol: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        result = score_pair(symbol, data_by_symbol.get(symbol, {}))
        rows.append({
            "symbol": result.symbol,
            "tradable": result.tradable,
            "score": result.score,
            "reasons": "|".join(result.reasons),
            "bars": result.bars,
            "avg_quote_volume": result.avg_quote_volume,
            "atr_pct": result.atr_pct,
            "funding_abs": result.funding_abs,
        })
    return pd.DataFrame(rows).sort_values(["tradable", "score"], ascending=[False, False])


def select_symbols(symbols: list[str], data_by_symbol: dict[str, dict]) -> list[str]:
    if not getattr(config, "PAIR_UNIVERSE_ENABLED", False):
        return list(symbols)
    report = score_universe(symbols, data_by_symbol)
    selected = report.loc[report["tradable"], "symbol"].tolist()
    return selected or list(symbols)
