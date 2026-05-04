from __future__ import annotations

import argparse
import json
from typing import Any

import ccxt
import pandas as pd

import config


FUNDING_INTERVALS_PER_YEAR = 3 * 365


def annualized_funding_apr(avg_funding_rate: float) -> float:
    return float(avg_funding_rate) * FUNDING_INTERVALS_PER_YEAR * 100.0


def paired_entry_exit_cost_pct(
    *,
    taker_fee_rate: float | None = None,
    slippage_rate_round_trip: float | None = None,
) -> float:
    """Approximate one full spot-long/perp-short open+close cost as percent.

    Four taker legs are assumed: spot buy, perp short, spot sell, perp cover.
    Slippage is modeled as one round-trip rate per leg pair and intentionally
    conservative until real fill calibration exists.
    """
    fee = float(taker_fee_rate if taker_fee_rate is not None else getattr(config, "TAKER_FEE_RATE", 0.0004))
    slip = float(
        slippage_rate_round_trip
        if slippage_rate_round_trip is not None
        else getattr(config, "SLIPPAGE_RATE_ROUND_TRIP", 0.0015)
    )
    return (4.0 * fee + 2.0 * slip) * 100.0


def summarize_funding_rates(
    rates: pd.DataFrame,
    *,
    symbol: str,
    min_samples: int = 30,
    earn_apr_benchmark_pct: float = 6.0,
) -> dict[str, Any]:
    if rates.empty or "funding_rate" not in rates.columns:
        return {
            "symbol": symbol,
            "samples": 0,
            "ok": False,
            "reason": "no_funding_data",
        }
    values = pd.to_numeric(rates["funding_rate"], errors="coerce").dropna()
    if values.empty:
        return {
            "symbol": symbol,
            "samples": 0,
            "ok": False,
            "reason": "no_numeric_funding_data",
        }
    avg = float(values.mean())
    gross = annualized_funding_apr(avg)
    entry_exit_cost = paired_entry_exit_cost_pct()
    net_vs_earn = gross - entry_exit_cost - float(earn_apr_benchmark_pct)
    positive_ratio = float((values > 0).sum() / len(values))
    return {
        "symbol": symbol,
        "samples": int(len(values)),
        "start": rates.index.min().isoformat() if isinstance(rates.index, pd.DatetimeIndex) else "",
        "end": rates.index.max().isoformat() if isinstance(rates.index, pd.DatetimeIndex) else "",
        "avg_funding_rate": round(avg, 10),
        "median_funding_rate": round(float(values.median()), 10),
        "positive_ratio_pct": round(positive_ratio * 100.0, 4),
        "gross_funding_apr_pct": round(gross, 4),
        "paired_entry_exit_cost_pct": round(entry_exit_cost, 4),
        "earn_apr_benchmark_pct": float(earn_apr_benchmark_pct),
        "net_apr_after_cost_vs_earn_pct": round(net_vs_earn, 4),
        "ok": bool(len(values) >= min_samples and net_vs_earn > 0 and positive_ratio >= 0.55),
        "reason": "" if len(values) >= min_samples else "insufficient_samples",
    }


def fetch_funding_history(exchange: ccxt.Exchange, symbol: str, *, days: int = 180) -> pd.DataFrame:
    since = exchange.milliseconds() - int(days * 24 * 60 * 60 * 1000)
    rows: list[dict[str, Any]] = []
    while since < exchange.milliseconds():
        batch = exchange.fetch_funding_rate_history(symbol, since=since, limit=1000)
        if not batch:
            break
        for item in batch:
            ts = item.get("timestamp")
            rate = item.get("fundingRate")
            if ts is None or rate is None:
                continue
            rows.append({
                "timestamp": pd.to_datetime(ts, unit="ms", utc=True),
                "funding_rate": float(rate),
            })
        last_ts = batch[-1].get("timestamp")
        if last_ts is None or last_ts <= since or len(batch) < 1000:
            break
        since = int(last_ts) + 1
    if not rows:
        return pd.DataFrame(columns=["funding_rate"])
    df = pd.DataFrame(rows).drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    return df.set_index("timestamp")


def scan_symbols(
    symbols: list[str],
    *,
    days: int = 180,
    earn_apr_benchmark_pct: float = 6.0,
) -> pd.DataFrame:
    exchange = ccxt.binance({"options": {"defaultType": "future"}})
    rows = []
    for symbol in symbols:
        rates = fetch_funding_history(exchange, symbol, days=days)
        rows.append(summarize_funding_rates(
            rates,
            symbol=symbol,
            earn_apr_benchmark_pct=earn_apr_benchmark_pct,
        ))
    return pd.DataFrame(rows).sort_values("net_apr_after_cost_vs_earn_pct", ascending=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Research scanner for funding-carry / delta-neutral candidates.")
    parser.add_argument("--symbols", nargs="*", default=list(getattr(config, "SYMBOLS", [])))
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--earn-apr", type=float, default=6.0)
    parser.add_argument("--out", default="carry_candidates.csv")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = scan_symbols(args.symbols, days=args.days, earn_apr_benchmark_pct=args.earn_apr)
    if args.out:
        result.to_csv(args.out, index=False)
    if args.json:
        print(json.dumps(result.to_dict(orient="records"), indent=2, sort_keys=True))
    else:
        print(result.to_string(index=False))
        if args.out:
            print(f"Output: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
