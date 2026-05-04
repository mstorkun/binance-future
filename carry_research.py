from __future__ import annotations

import argparse
import json
import re
from typing import Any

import ccxt
import pandas as pd

import config


FUNDING_INTERVALS_PER_YEAR = 3 * 365
DEFAULT_MIN_QUOTE_VOLUME_USDT = 50_000_000.0
DEFAULT_MAX_SYMBOLS = 80
SAFE_BASE_RE = re.compile(r"^[A-Z0-9]+$")


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


def carry_backtest_from_rates(
    rates: pd.DataFrame,
    *,
    symbol: str,
    notional_usdt: float = 1000.0,
    earn_apr_benchmark_pct: float = 6.0,
    entry_exit_cost_pct: float | None = None,
) -> dict[str, Any]:
    if rates.empty or "funding_rate" not in rates.columns:
        return {
            "symbol": symbol,
            "periods": 0,
            "ok": False,
            "reason": "no_funding_data",
        }
    values = pd.to_numeric(rates["funding_rate"], errors="coerce").dropna().sort_index()
    if values.empty:
        return {
            "symbol": symbol,
            "periods": 0,
            "ok": False,
            "reason": "no_numeric_funding_data",
        }

    start = values.index.min()
    end = values.index.max()
    days = max((end - start).total_seconds() / 86400.0, len(values) / 3.0) if isinstance(values.index, pd.DatetimeIndex) else len(values) / 3.0
    cost_pct = float(entry_exit_cost_pct if entry_exit_cost_pct is not None else paired_entry_exit_cost_pct())
    gross_funding_pct = float(values.sum() * 100.0)
    net_after_cost_pct = gross_funding_pct - cost_pct
    earn_pct_for_period = float(earn_apr_benchmark_pct) * days / 365.0
    net_vs_earn_pct = net_after_cost_pct - earn_pct_for_period

    pnl_pct_path = values.cumsum() * 100.0 - cost_pct
    equity = float(notional_usdt) * (1.0 + pnl_pct_path / 100.0)
    peak = equity.cummax()
    drawdown = (peak - equity) / peak.replace(0, pd.NA) * 100.0

    annualized_net_after_cost_pct = net_after_cost_pct * 365.0 / days if days > 0 else 0.0
    positive_ratio = float((values > 0).sum() / len(values))
    return {
        "symbol": symbol,
        "periods": int(len(values)),
        "start": start.isoformat() if hasattr(start, "isoformat") else "",
        "end": end.isoformat() if hasattr(end, "isoformat") else "",
        "days": round(float(days), 4),
        "notional_usdt": float(notional_usdt),
        "gross_funding_pct": round(gross_funding_pct, 4),
        "entry_exit_cost_pct": round(cost_pct, 4),
        "net_after_cost_pct": round(net_after_cost_pct, 4),
        "earn_benchmark_pct_for_period": round(earn_pct_for_period, 4),
        "net_vs_earn_pct": round(net_vs_earn_pct, 4),
        "annualized_net_after_cost_pct": round(annualized_net_after_cost_pct, 4),
        "positive_ratio_pct": round(positive_ratio * 100.0, 4),
        "negative_ratio_pct": round((1.0 - positive_ratio) * 100.0, 4),
        "worst_funding_rate": round(float(values.min()), 10),
        "best_funding_rate": round(float(values.max()), 10),
        "max_drawdown_pct": round(float(drawdown.max(skipna=True) or 0.0), 4),
        "ok": bool(net_vs_earn_pct > 0 and positive_ratio >= 0.55),
        "reason": "",
    }


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
    entry_exit_cost = paired_entry_exit_cost_pct()
    backtest = carry_backtest_from_rates(
        rates,
        symbol=symbol,
        earn_apr_benchmark_pct=earn_apr_benchmark_pct,
        entry_exit_cost_pct=entry_exit_cost,
    )
    avg = float(values.mean())
    gross = float(backtest.get("gross_funding_pct", 0.0)) * 365.0 / max(float(backtest.get("days", 0.0)), 1e-9)
    net_vs_earn = float(backtest.get("annualized_net_after_cost_pct", 0.0)) - float(earn_apr_benchmark_pct)
    positive_ratio = float((values > 0).sum() / len(values))
    summary = {
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
    summary.update({
        "bt_net_after_cost_pct": backtest.get("net_after_cost_pct", 0.0),
        "bt_earn_benchmark_pct": backtest.get("earn_benchmark_pct_for_period", 0.0),
        "bt_net_vs_earn_pct": backtest.get("net_vs_earn_pct", 0.0),
        "bt_max_drawdown_pct": backtest.get("max_drawdown_pct", 0.0),
        "bt_annualized_net_after_cost_pct": backtest.get("annualized_net_after_cost_pct", 0.0),
        "worst_funding_rate": backtest.get("worst_funding_rate", 0.0),
        "best_funding_rate": backtest.get("best_funding_rate", 0.0),
    })
    return summary


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


def quote_volume_usdt(ticker: dict[str, Any]) -> float:
    quote = ticker.get("quoteVolume")
    if quote is not None:
        return float(quote)
    info = ticker.get("info") or {}
    for key in ("quoteVolume", "quoteVolume24h"):
        if info.get(key) is not None:
            return float(info[key])
    base = ticker.get("baseVolume")
    last = ticker.get("last") or ticker.get("close")
    if base is not None and last is not None:
        return float(base) * float(last)
    return 0.0


def spot_symbol_for_market(market: dict[str, Any]) -> str:
    return f"{market.get('base')}/{market.get('quote')}"


def discover_carry_universe(
    exchange: ccxt.Exchange | None = None,
    spot_exchange: ccxt.Exchange | None = None,
    *,
    min_quote_volume_usdt: float = DEFAULT_MIN_QUOTE_VOLUME_USDT,
    max_symbols: int = DEFAULT_MAX_SYMBOLS,
    ascii_only: bool = True,
) -> pd.DataFrame:
    futures = exchange or ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    spot = spot_exchange or ccxt.binance({"enableRateLimit": True})
    futures_markets = futures.load_markets()
    spot_markets = spot.load_markets()

    candidates: list[dict[str, Any]] = []
    for symbol, market in futures_markets.items():
        if not market.get("active", True):
            continue
        if not market.get("swap") or not market.get("linear"):
            continue
        if market.get("quote") != "USDT" or market.get("settle") != "USDT":
            continue
        base = str(market.get("base") or "")
        if ascii_only and not SAFE_BASE_RE.match(base):
            continue
        spot_symbol = spot_symbol_for_market(market)
        spot_market = spot_markets.get(spot_symbol)
        if not spot_market or not spot_market.get("active", True) or not spot_market.get("spot"):
            continue
        candidates.append({
            "symbol": symbol,
            "spot_symbol": spot_symbol,
            "base": base,
            "quote": market.get("quote"),
        })

    tickers = futures.fetch_tickers([row["symbol"] for row in candidates]) if candidates else {}
    rows: list[dict[str, Any]] = []
    for row in candidates:
        ticker = tickers.get(row["symbol"], {})
        volume = quote_volume_usdt(ticker)
        if volume < float(min_quote_volume_usdt):
            continue
        rows.append({
            **row,
            "quote_volume_usdt": round(volume, 2),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["symbol", "spot_symbol", "base", "quote", "quote_volume_usdt"])
    return df.sort_values("quote_volume_usdt", ascending=False).head(int(max_symbols)).reset_index(drop=True)


def scan_symbols(
    symbols: list[str],
    *,
    days: int = 180,
    earn_apr_benchmark_pct: float = 6.0,
    min_samples: int = 30,
    exchange: ccxt.Exchange | None = None,
) -> pd.DataFrame:
    exchange = exchange or ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    rows = []
    for symbol in symbols:
        rates = fetch_funding_history(exchange, symbol, days=days)
        rows.append(summarize_funding_rates(
            rates,
            symbol=symbol,
            min_samples=min_samples,
            earn_apr_benchmark_pct=earn_apr_benchmark_pct,
        ))
    return pd.DataFrame(rows).sort_values("net_apr_after_cost_vs_earn_pct", ascending=False)


def scan_auto_universe(
    *,
    days: int = 180,
    earn_apr_benchmark_pct: float = 6.0,
    min_quote_volume_usdt: float = DEFAULT_MIN_QUOTE_VOLUME_USDT,
    max_symbols: int = DEFAULT_MAX_SYMBOLS,
    min_samples: int = 30,
    ascii_only: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    spot_exchange = ccxt.binance({"enableRateLimit": True})
    universe = discover_carry_universe(
        exchange,
        spot_exchange,
        min_quote_volume_usdt=min_quote_volume_usdt,
        max_symbols=max_symbols,
        ascii_only=ascii_only,
    )
    if universe.empty:
        return universe, pd.DataFrame()
    result = scan_symbols(
        universe["symbol"].tolist(),
        days=days,
        earn_apr_benchmark_pct=earn_apr_benchmark_pct,
        min_samples=min_samples,
        exchange=exchange,
    )
    result = result.merge(universe, on="symbol", how="left")
    return universe, result.sort_values("net_apr_after_cost_vs_earn_pct", ascending=False).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Research scanner for funding-carry / delta-neutral candidates.")
    parser.add_argument("--symbols", nargs="*", default=list(getattr(config, "SYMBOLS", [])))
    parser.add_argument("--auto-universe", action="store_true", help="Discover liquid USDT perpetuals with active spot pairs.")
    parser.add_argument("--min-quote-volume-usdt", type=float, default=DEFAULT_MIN_QUOTE_VOLUME_USDT)
    parser.add_argument("--max-symbols", type=int, default=DEFAULT_MAX_SYMBOLS)
    parser.add_argument("--min-samples", type=int, default=None)
    parser.add_argument("--include-non-ascii", action="store_true")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--earn-apr", type=float, default=6.0)
    parser.add_argument("--out", default="carry_candidates.csv")
    parser.add_argument("--universe-out", default="carry_universe.csv")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.auto_universe:
        min_samples = args.min_samples if args.min_samples is not None else max(30, int(args.days * 2))
        universe, result = scan_auto_universe(
            days=args.days,
            earn_apr_benchmark_pct=args.earn_apr,
            min_quote_volume_usdt=args.min_quote_volume_usdt,
            max_symbols=args.max_symbols,
            min_samples=min_samples,
            ascii_only=not args.include_non_ascii,
        )
        if args.universe_out:
            universe.to_csv(args.universe_out, index=False)
    else:
        min_samples = args.min_samples if args.min_samples is not None else 30
        result = scan_symbols(
            args.symbols,
            days=args.days,
            earn_apr_benchmark_pct=args.earn_apr,
            min_samples=min_samples,
        )
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
