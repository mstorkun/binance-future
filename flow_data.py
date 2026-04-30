"""
Binance USD-M futures flow context.

These public datasets are useful in live/testnet mode, but some endpoints expose
only a recent window. The module therefore treats flow as an optional risk
overlay instead of a mandatory historical feature.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import pandas as pd

import config

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FlowFetchResult:
    data: pd.DataFrame
    warnings: tuple[str, ...] = ()


def _market_id(symbol: str) -> str:
    return symbol.replace("/", "").replace(":USDT", "").upper()


def _timeframe_delta(period: str) -> pd.Timedelta:
    unit = period[-1]
    value = int(period[:-1])
    if unit == "m":
        return pd.Timedelta(minutes=value)
    if unit == "h":
        return pd.Timedelta(hours=value)
    if unit == "d":
        return pd.Timedelta(days=value)
    return pd.Timedelta(hours=4)


def _utc_naive(ts) -> pd.Timestamp:
    out = pd.Timestamp(ts)
    if out.tzinfo is not None:
        out = out.tz_convert("UTC").tz_localize(None)
    return out


def _call(exchange, method: str, params: dict[str, Any]) -> Any:
    fn = getattr(exchange, method, None)
    if fn is None:
        raise AttributeError(method)
    return fn(params)


def _rows_to_df(rows: list[dict[str, Any]], value_map: dict[str, str]) -> pd.DataFrame:
    parsed = []
    for row in rows or []:
        ts = row.get("timestamp")
        if ts is None:
            continue
        item = {"timestamp": pd.to_datetime(int(ts), unit="ms")}
        for src, dst in value_map.items():
            try:
                item[dst] = float(row[src])
            except (KeyError, TypeError, ValueError):
                pass
        parsed.append(item)
    if not parsed:
        return pd.DataFrame()
    df = pd.DataFrame(parsed).set_index("timestamp").sort_index()
    return df[~df.index.duplicated(keep="last")]


def fetch_recent_flow(exchange, symbol: str, period: str | None = None, limit: int | None = None) -> FlowFetchResult:
    """Fetch recent futures flow datasets through Binance public endpoints."""
    if not getattr(config, "FLOW_DATA_ENABLED", True):
        return FlowFetchResult(pd.DataFrame(), ())

    period = period or getattr(config, "FLOW_PERIOD", config.TIMEFRAME)
    limit = limit or getattr(config, "FLOW_HISTORY_LIMIT", 500)
    params = {"symbol": _market_id(symbol), "period": period, "limit": limit}
    frames: list[pd.DataFrame] = []
    warnings: list[str] = []

    try:
        rows = _call(exchange, "fapiDataGetOpenInterestHist", params)
        oi = _rows_to_df(rows, {
            "sumOpenInterest": "flow_open_interest",
            "sumOpenInterestValue": "flow_open_interest_value",
        })
        if not oi.empty:
            oi["flow_oi_change"] = oi["flow_open_interest"].pct_change(3)
            frames.append(oi)
    except Exception as e:
        warnings.append(f"open_interest_hist:{e}")

    try:
        rows = _call(exchange, "fapiDataGetTakerlongshortRatio", params)
        taker = _rows_to_df(rows, {
            "buySellRatio": "flow_taker_buy_sell_ratio",
            "buyVol": "flow_taker_buy_volume",
            "sellVol": "flow_taker_sell_volume",
        })
        if not taker.empty:
            total = taker["flow_taker_buy_volume"] + taker["flow_taker_sell_volume"]
            taker["flow_taker_buy_ratio"] = taker["flow_taker_buy_volume"] / total.replace(0, pd.NA)
            frames.append(taker)
    except Exception as e:
        warnings.append(f"taker_buy_sell:{e}")

    try:
        rows = _call(exchange, "fapiDataGetTopLongShortPositionRatio", params)
        top = _rows_to_df(rows, {
            "longShortRatio": "flow_top_long_short_ratio",
            "longAccount": "flow_top_long_account",
            "shortAccount": "flow_top_short_account",
        })
        if not top.empty:
            frames.append(top)
    except Exception as e:
        warnings.append(f"top_trader_ratio:{e}")

    try:
        premium = _call(exchange, "fapiPublicGetPremiumIndex", {"symbol": _market_id(symbol)})
        if isinstance(premium, dict):
            now_ts = premium.get("time")
            if now_ts is not None:
                mark = pd.DataFrame([{
                    "timestamp": pd.to_datetime(int(now_ts), unit="ms"),
                    "flow_mark_price": float(premium.get("markPrice", 0) or 0),
                    "flow_index_price": float(premium.get("indexPrice", 0) or 0),
                    "flow_funding_rate": float(premium.get("lastFundingRate", 0) or 0),
                }]).set_index("timestamp")
                frames.append(mark)
    except Exception as e:
        warnings.append(f"premium_index:{e}")

    if not frames:
        return FlowFetchResult(pd.DataFrame(), tuple(warnings))

    out = pd.concat(frames, axis=1).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return FlowFetchResult(out, tuple(warnings))


def add_flow_indicators(df: pd.DataFrame, flow: pd.DataFrame | None, period: str | None = None) -> pd.DataFrame:
    """Merge flow context into candle data without using future flow buckets."""
    if flow is None or flow.empty:
        return df

    out = df.copy()
    ctx = flow.copy().sort_index()
    snapshot_cols = [
        col for col in ("flow_mark_price", "flow_index_price", "flow_funding_rate")
        if col in ctx.columns
    ]
    bucket_cols = [col for col in ctx.columns if col not in snapshot_cols]

    aligned = pd.DataFrame(index=out.index)
    max_age = float(getattr(config, "FLOW_MAX_AGE_MINUTES", 300))
    fresh_parts: list[pd.Series] = []
    if bucket_cols:
        buckets = ctx[bucket_cols].copy()
        buckets.index = buckets.index + _timeframe_delta(period or getattr(config, "FLOW_PERIOD", config.TIMEFRAME))
        aligned = buckets.reindex(out.index, method="ffill")
        bucket_times = pd.Series(buckets.index, index=buckets.index).reindex(out.index, method="ffill")
        bucket_age = pd.Series(pd.NA, index=out.index, dtype="Float64")
        valid_times = bucket_times.notna()
        if valid_times.any():
            bucket_age.loc[valid_times] = [
                (idx - _utc_naive(bucket_times.loc[idx])).total_seconds() / 60.0
                for idx in out.index[valid_times]
            ]
        out["flow_bucket_age_minutes"] = bucket_age
        bucket_fresh = bucket_age.notna() & (bucket_age <= max_age)
        fresh_parts.append(bucket_fresh.astype(bool))
        stale_mask = ~bucket_fresh.fillna(False)
        for col in bucket_cols:
            aligned.loc[stale_mask, col] = pd.NA

    for col in aligned.columns:
        out[col] = aligned[col]

    # Premium index / latest funding is a current snapshot, not a historical
    # bucket. In live/testnet mode it is valid for the current decision bar.
    snapshot_fresh = pd.Series(False, index=out.index)
    for col in snapshot_cols:
        values = ctx[col].dropna()
        if values.empty or len(out) < 2:
            continue
        snapshot_ts = _utc_naive(values.index[-1])
        now_utc = pd.Timestamp.now(tz="UTC").tz_localize(None)
        snapshot_age = (now_utc - snapshot_ts).total_seconds() / 60.0
        out.loc[out.index[-2:], "flow_snapshot_age_minutes"] = snapshot_age
        if snapshot_age <= max_age:
            out.loc[out.index[-2:], col] = float(values.iloc[-1])
            snapshot_fresh.loc[out.index[-2:]] = True

    if snapshot_cols:
        fresh_parts.append(snapshot_fresh)
    if fresh_parts:
        out["flow_fresh"] = pd.concat(fresh_parts, axis=1).any(axis=1)
    return out


def warn_once_for_flow(result: FlowFetchResult, symbol: str) -> None:
    if result.warnings:
        log.warning("[%s] Flow data partially unavailable: %s", symbol, "; ".join(result.warnings[:3]))
