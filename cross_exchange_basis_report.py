from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import ccxt
import pandas as pd

import carry_research


DEFAULT_EXCHANGES = ("binance", "okx", "bybit")


def make_exchange(exchange_id: str) -> ccxt.Exchange:
    options = {"defaultType": "swap"} if exchange_id == "okx" else {"defaultType": "future"}
    exchange_class = getattr(ccxt, exchange_id)
    return exchange_class({"enableRateLimit": True, "options": options})


def funding_series(rates: pd.DataFrame) -> pd.Series:
    if rates.empty or "funding_rate" not in rates.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(rates["funding_rate"], errors="coerce").dropna().sort_index()


def align_funding_rates(exchange_rates: dict[str, pd.DataFrame]) -> pd.DataFrame:
    series = {name: funding_series(rates) for name, rates in exchange_rates.items()}
    series = {name: values for name, values in series.items() if not values.empty}
    if len(series) < 2:
        return pd.DataFrame()
    frame = pd.concat(series, axis=1, join="inner").dropna().sort_index()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [str(col[0]) for col in frame.columns]
    return frame


def fold_days(test: pd.DataFrame) -> float:
    if test.empty:
        return 0.0
    if isinstance(test.index, pd.DatetimeIndex) and len(test) > 1:
        elapsed = (test.index.max() - test.index.min()).total_seconds() / 86400.0
        return max(float(elapsed), len(test) / carry_research.FUNDING_INTERVALS_PER_YEAR * 365.0)
    return len(test) / carry_research.FUNDING_INTERVALS_PER_YEAR * 365.0


def evaluate_exchange_pair_fold(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    symbol: str,
    exchange_a: str,
    exchange_b: str,
    fold: int = 0,
    entry_exit_cost_pct: float | None = None,
    earn_apr_benchmark_pct: float = 6.0,
    min_test_samples: int = 30,
) -> dict[str, Any]:
    if train.empty or test.empty:
        return {
            "symbol": symbol,
            "exchange_a": exchange_a,
            "exchange_b": exchange_b,
            "fold": int(fold),
            "ok": False,
            "reason": "empty_fold",
        }
    train_diff = train[exchange_a] - train[exchange_b]
    direction_sign = 1.0 if float(train_diff.mean()) >= 0.0 else -1.0
    short_exchange = exchange_a if direction_sign > 0 else exchange_b
    long_exchange = exchange_b if direction_sign > 0 else exchange_a
    test_spread = direction_sign * (test[exchange_a] - test[exchange_b])
    days = fold_days(test)
    cost_pct = float(entry_exit_cost_pct if entry_exit_cost_pct is not None else carry_research.paired_entry_exit_cost_pct())
    gross_spread_pct = float(test_spread.sum() * 100.0)
    net_after_cost_pct = gross_spread_pct - cost_pct
    earn_pct = float(earn_apr_benchmark_pct) * days / 365.0
    net_vs_earn_pct = net_after_cost_pct - earn_pct
    positive_ratio = float((test_spread > 0).mean() * 100.0) if len(test_spread) else 0.0
    annualized_net_pct = net_after_cost_pct * 365.0 / days if days > 0 else 0.0
    annualized_gross_pct = gross_spread_pct * 365.0 / days if days > 0 else 0.0
    ok = bool(len(test_spread) >= int(min_test_samples) and net_vs_earn_pct > 0.0 and positive_ratio >= 55.0)
    return {
        "symbol": symbol,
        "exchange_a": exchange_a,
        "exchange_b": exchange_b,
        "pair": f"{exchange_a}/{exchange_b}",
        "fold": int(fold),
        "train_start": train.index.min().isoformat() if hasattr(train.index.min(), "isoformat") else "",
        "train_end": train.index.max().isoformat() if hasattr(train.index.max(), "isoformat") else "",
        "test_start": test.index.min().isoformat() if hasattr(test.index.min(), "isoformat") else "",
        "test_end": test.index.max().isoformat() if hasattr(test.index.max(), "isoformat") else "",
        "train_samples": int(len(train)),
        "test_samples": int(len(test)),
        "short_exchange": short_exchange,
        "long_exchange": long_exchange,
        "train_mean_spread_pct": round(float(direction_sign * train_diff.mean() * 100.0), 6),
        "test_mean_spread_pct": round(float(test_spread.mean() * 100.0), 6),
        "gross_spread_pct": round(gross_spread_pct, 6),
        "entry_exit_cost_pct": round(cost_pct, 6),
        "net_after_cost_pct": round(net_after_cost_pct, 6),
        "earn_benchmark_pct_for_period": round(earn_pct, 6),
        "net_vs_earn_pct": round(net_vs_earn_pct, 6),
        "annualized_gross_spread_pct": round(annualized_gross_pct, 4),
        "annualized_net_after_cost_pct": round(annualized_net_pct, 4),
        "positive_spread_ratio_pct": round(positive_ratio, 4),
        "ok": ok,
        "reason": "" if ok else "insufficient_oos_basis_edge",
    }


def walk_forward_exchange_pair(
    aligned: pd.DataFrame,
    *,
    symbol: str,
    exchange_a: str,
    exchange_b: str,
    train_samples: int = 240,
    test_samples: int = 60,
    roll_samples: int = 60,
    min_folds: int = 3,
    min_test_samples: int = 30,
    earn_apr_benchmark_pct: float = 6.0,
    entry_exit_cost_pct: float | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    columns = [exchange_a, exchange_b]
    frame = aligned[columns].dropna().sort_index() if set(columns).issubset(aligned.columns) else pd.DataFrame()
    if frame.empty:
        return {
            "symbol": symbol,
            "pair": f"{exchange_a}/{exchange_b}",
            "samples": 0,
            "folds": 0,
            "ok_folds": 0,
            "test_samples": 0,
            "gross_spread_pct": 0.0,
            "net_after_cost_pct": 0.0,
            "net_vs_earn_pct": 0.0,
            "avg_annualized_net_after_cost_pct": 0.0,
            "avg_positive_spread_ratio_pct": 0.0,
            "ok": False,
            "reason": "no_aligned_funding_data",
        }, []

    folds: list[dict[str, Any]] = []
    start = 0
    fold = 0
    train_samples = int(train_samples)
    test_samples = int(test_samples)
    roll_samples = int(roll_samples)
    while start + train_samples < len(frame):
        train = frame.iloc[start : start + train_samples]
        test = frame.iloc[start + train_samples : start + train_samples + test_samples]
        if test.empty:
            break
        if len(test) < int(min_test_samples):
            break
        folds.append(
            evaluate_exchange_pair_fold(
                train,
                test,
                symbol=symbol,
                exchange_a=exchange_a,
                exchange_b=exchange_b,
                fold=fold,
                entry_exit_cost_pct=entry_exit_cost_pct,
                earn_apr_benchmark_pct=earn_apr_benchmark_pct,
                min_test_samples=min_test_samples,
            )
        )
        if start + train_samples + test_samples >= len(frame):
            break
        start += roll_samples
        fold += 1

    if not folds:
        return {
            "symbol": symbol,
            "pair": f"{exchange_a}/{exchange_b}",
            "samples": int(len(frame)),
            "folds": 0,
            "ok_folds": 0,
            "test_samples": 0,
            "gross_spread_pct": 0.0,
            "net_after_cost_pct": 0.0,
            "net_vs_earn_pct": 0.0,
            "avg_annualized_net_after_cost_pct": 0.0,
            "avg_positive_spread_ratio_pct": 0.0,
            "ok": False,
            "reason": "insufficient_samples_for_walk_forward",
        }, []

    ok_folds = sum(1 for row in folds if row.get("ok"))
    test_total = sum(int(row.get("test_samples", 0) or 0) for row in folds)
    net_vs_earn_total = sum(float(row.get("net_vs_earn_pct", 0.0) or 0.0) for row in folds)
    net_after_cost_total = sum(float(row.get("net_after_cost_pct", 0.0) or 0.0) for row in folds)
    gross_total = sum(float(row.get("gross_spread_pct", 0.0) or 0.0) for row in folds)
    avg_annualized_net = (
        sum(float(row.get("annualized_net_after_cost_pct", 0.0) or 0.0) * int(row.get("test_samples", 0) or 0) for row in folds)
        / max(test_total, 1)
    )
    avg_positive_ratio = (
        sum(float(row.get("positive_spread_ratio_pct", 0.0) or 0.0) * int(row.get("test_samples", 0) or 0) for row in folds)
        / max(test_total, 1)
    )
    ok = bool(len(folds) >= int(min_folds) and ok_folds == len(folds) and net_vs_earn_total > 0.0)
    reason = ""
    if not ok:
        reason = "insufficient_oos_folds" if len(folds) < int(min_folds) else "insufficient_oos_basis_edge"
    return {
        "symbol": symbol,
        "pair": f"{exchange_a}/{exchange_b}",
        "samples": int(len(frame)),
        "folds": int(len(folds)),
        "ok_folds": int(ok_folds),
        "test_samples": int(test_total),
        "gross_spread_pct": round(gross_total, 6),
        "net_after_cost_pct": round(net_after_cost_total, 6),
        "net_vs_earn_pct": round(net_vs_earn_total, 6),
        "avg_annualized_net_after_cost_pct": round(float(avg_annualized_net), 4),
        "avg_positive_spread_ratio_pct": round(float(avg_positive_ratio), 4),
        "ok": ok,
        "reason": reason,
    }, folds


def active_usdt_swap_symbols(exchange: ccxt.Exchange, *, ascii_only: bool = True) -> dict[str, str]:
    markets = exchange.load_markets()
    rows: dict[str, str] = {}
    for symbol, market in markets.items():
        if not market.get("active", True):
            continue
        if not market.get("swap") or not market.get("linear"):
            continue
        if market.get("quote") != "USDT" or market.get("settle") != "USDT":
            continue
        base = str(market.get("base") or "")
        if ascii_only and not carry_research.SAFE_BASE_RE.match(base):
            continue
        rows[base] = symbol
    return rows


def discover_common_universe(
    exchanges: dict[str, ccxt.Exchange],
    *,
    min_quote_volume_usdt: float = carry_research.DEFAULT_MIN_QUOTE_VOLUME_USDT,
    max_symbols: int = carry_research.DEFAULT_MAX_SYMBOLS,
    ascii_only: bool = True,
) -> pd.DataFrame:
    symbols_by_exchange = {
        name: active_usdt_swap_symbols(exchange, ascii_only=ascii_only)
        for name, exchange in exchanges.items()
    }
    if len(symbols_by_exchange) < 2:
        return pd.DataFrame()
    common_bases = set.intersection(*(set(rows) for rows in symbols_by_exchange.values()))
    binance = exchanges.get("binance") or next(iter(exchanges.values()))
    binance_symbols = [symbols_by_exchange.get("binance", {}).get(base) for base in common_bases]
    binance_symbols = [symbol for symbol in binance_symbols if symbol]
    tickers = binance.fetch_tickers(binance_symbols) if binance_symbols else {}
    rows: list[dict[str, Any]] = []
    for base in common_bases:
        symbol_map = {name: by_base[base] for name, by_base in symbols_by_exchange.items() if base in by_base}
        anchor_symbol = symbol_map.get("binance") or next(iter(symbol_map.values()))
        volume = carry_research.quote_volume_usdt(tickers.get(anchor_symbol, {}))
        if volume < float(min_quote_volume_usdt):
            continue
        rows.append({
            "base": base,
            "symbol": anchor_symbol,
            "quote_volume_usdt": round(float(volume), 2),
            "exchange_symbols": json.dumps(symbol_map, sort_keys=True),
        })
    if not rows:
        return pd.DataFrame(columns=["base", "symbol", "quote_volume_usdt", "exchange_symbols"])
    return pd.DataFrame(rows).sort_values("quote_volume_usdt", ascending=False).head(int(max_symbols)).reset_index(drop=True)


def scan_symbol(
    exchanges: dict[str, ccxt.Exchange],
    symbol_map: dict[str, str],
    *,
    base: str,
    days: int = 180,
    train_samples: int = 240,
    test_samples: int = 60,
    roll_samples: int = 60,
    min_folds: int = 3,
    min_test_samples: int = 30,
    earn_apr_benchmark_pct: float = 6.0,
    entry_exit_cost_pct: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rates: dict[str, pd.DataFrame] = {}
    for exchange_name, symbol in symbol_map.items():
        rates[exchange_name] = carry_research.fetch_funding_history(exchanges[exchange_name], symbol, days=days)
    aligned = align_funding_rates(rates)
    summaries: list[dict[str, Any]] = []
    folds: list[dict[str, Any]] = []
    exchange_names = sorted(aligned.columns.tolist())
    for i, exchange_a in enumerate(exchange_names):
        for exchange_b in exchange_names[i + 1 :]:
            summary, pair_folds = walk_forward_exchange_pair(
                aligned,
                symbol=f"{base}/USDT:USDT",
                exchange_a=exchange_a,
                exchange_b=exchange_b,
                train_samples=train_samples,
                test_samples=test_samples,
                roll_samples=roll_samples,
                min_folds=min_folds,
                min_test_samples=min_test_samples,
                earn_apr_benchmark_pct=earn_apr_benchmark_pct,
                entry_exit_cost_pct=entry_exit_cost_pct,
            )
            summary["base"] = base
            summaries.append(summary)
            folds.extend(pair_folds)
    if not summaries:
        summaries.append({
            "symbol": f"{base}/USDT:USDT",
            "base": base,
            "pair": "",
            "samples": int(len(aligned)),
            "folds": 0,
            "ok_folds": 0,
            "test_samples": 0,
            "gross_spread_pct": 0.0,
            "net_after_cost_pct": 0.0,
            "net_vs_earn_pct": 0.0,
            "avg_annualized_net_after_cost_pct": 0.0,
            "avg_positive_spread_ratio_pct": 0.0,
            "ok": False,
            "reason": "insufficient_exchange_overlap",
        })
    return summaries, folds


def scan_auto_universe(
    *,
    exchange_ids: tuple[str, ...] = DEFAULT_EXCHANGES,
    days: int = 180,
    min_quote_volume_usdt: float = carry_research.DEFAULT_MIN_QUOTE_VOLUME_USDT,
    max_symbols: int = carry_research.DEFAULT_MAX_SYMBOLS,
    train_samples: int = 240,
    test_samples: int = 60,
    roll_samples: int = 60,
    min_folds: int = 3,
    min_test_samples: int = 30,
    earn_apr_benchmark_pct: float = 6.0,
    ascii_only: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    exchanges = {exchange_id: make_exchange(exchange_id) for exchange_id in exchange_ids}
    universe = discover_common_universe(
        exchanges,
        min_quote_volume_usdt=min_quote_volume_usdt,
        max_symbols=max_symbols,
        ascii_only=ascii_only,
    )
    summaries: list[dict[str, Any]] = []
    folds: list[dict[str, Any]] = []
    for row in universe.to_dict(orient="records"):
        symbol_map = json.loads(row["exchange_symbols"])
        symbol_summaries, symbol_folds = scan_symbol(
            exchanges,
            symbol_map,
            base=row["base"],
            days=days,
            train_samples=train_samples,
            test_samples=test_samples,
            roll_samples=roll_samples,
            min_folds=min_folds,
            min_test_samples=min_test_samples,
            earn_apr_benchmark_pct=earn_apr_benchmark_pct,
        )
        for summary in symbol_summaries:
            summary["quote_volume_usdt"] = row.get("quote_volume_usdt")
        summaries.extend(symbol_summaries)
        folds.extend(symbol_folds)
    result = pd.DataFrame(summaries)
    if not result.empty:
        result["has_folds"] = result["folds"].fillna(0).astype(int) > 0
        result = result.sort_values(
            ["ok", "has_folds", "folds", "net_vs_earn_pct", "avg_annualized_net_after_cost_pct"],
            ascending=[False, False, False, False, False],
        ).drop(columns=["has_folds"]).reset_index(drop=True)
    return universe, result, pd.DataFrame(folds)


def _format(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows._"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_format(row.get(col)) for col in columns) + " |")
    return "\n".join(lines)


def write_markdown(
    result: pd.DataFrame,
    folds: pd.DataFrame,
    universe: pd.DataFrame,
    path: str | Path,
    *,
    command: str,
    min_folds: int,
) -> None:
    pass_count = int(result["ok"].sum()) if "ok" in result.columns else 0
    if result.empty:
        rows = []
    else:
        ranked = result[result["folds"].fillna(0).astype(int) > 0]
        rows = (ranked if not ranked.empty else result).head(15).to_dict(orient="records")
    columns = [
        "symbol",
        "pair",
        "folds",
        "ok_folds",
        "net_vs_earn_pct",
        "avg_annualized_net_after_cost_pct",
        "avg_positive_spread_ratio_pct",
        "ok",
        "reason",
    ]
    lines = [
        "# Cross-Exchange Basis PoC - 2026-05-04",
        "",
        "This is a research-only Binance/OKX/Bybit perp funding-spread report.",
        "It does not create an executor, does not transfer collateral, and does",
        "not change paper/testnet/live behavior.",
        "",
        "## Method",
        "",
        "For each common liquid USDT perpetual, each exchange pair is evaluated",
        "with walk-forward folds. The short/long exchange direction is selected",
        "only from the train window. The test window then measures realized funding",
        "spread after conservative open/close costs and a USDT earn benchmark.",
        "",
        f"Strict pass gate: at least `{min_folds}` OOS folds, every fold must pass,",
        "and aggregate net funding must beat the benchmark after costs.",
        "",
        f"Command: `{command}`",
        "",
        "## Result",
        "",
        f"- Universe symbols: `{len(universe)}`",
        f"- Exchange-pair rows: `{len(result)}`",
        f"- Exchange-pair rows with OOS folds: `{int((result['folds'].fillna(0).astype(int) > 0).sum()) if not result.empty else 0}`",
        f"- Passing exchange-pair rows: `{pass_count}`",
        f"- Fold rows: `{len(folds)}`",
        "",
        markdown_table(rows, columns),
        "",
        "## Decision",
        "",
        "A pass here would still not be executor approval; it would only justify",
        "deeper work on exchange account constraints, transfer cost, collateral",
        "fragmentation, liquidation math, and fill probes. If pass count is zero,",
        "do not build a cross-exchange basis executor.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Research-only cross-exchange perp funding basis PoC.")
    parser.add_argument("--exchanges", nargs="*", default=list(DEFAULT_EXCHANGES))
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--min-quote-volume-usdt", type=float, default=carry_research.DEFAULT_MIN_QUOTE_VOLUME_USDT)
    parser.add_argument("--max-symbols", type=int, default=60)
    parser.add_argument("--train-samples", type=int, default=240)
    parser.add_argument("--test-samples", type=int, default=60)
    parser.add_argument("--roll-samples", type=int, default=60)
    parser.add_argument("--min-folds", type=int, default=3)
    parser.add_argument("--min-test-samples", type=int, default=30)
    parser.add_argument("--earn-apr", type=float, default=6.0)
    parser.add_argument("--include-non-ascii", action="store_true")
    parser.add_argument("--out", default="cross_exchange_basis_results.csv")
    parser.add_argument("--folds-out", default="cross_exchange_basis_folds.csv")
    parser.add_argument("--universe-out", default="cross_exchange_basis_universe.csv")
    parser.add_argument("--json-out", default="cross_exchange_basis_report.json")
    parser.add_argument("--md-out", default="docs/CROSS_EXCHANGE_BASIS_2026_05_04.md")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    universe, result, folds = scan_auto_universe(
        exchange_ids=tuple(args.exchanges),
        days=args.days,
        min_quote_volume_usdt=args.min_quote_volume_usdt,
        max_symbols=args.max_symbols,
        train_samples=args.train_samples,
        test_samples=args.test_samples,
        roll_samples=args.roll_samples,
        min_folds=args.min_folds,
        min_test_samples=args.min_test_samples,
        earn_apr_benchmark_pct=args.earn_apr,
        ascii_only=not args.include_non_ascii,
    )
    if args.out:
        result.to_csv(args.out, index=False)
    if args.folds_out:
        folds.to_csv(args.folds_out, index=False)
    if args.universe_out:
        universe.to_csv(args.universe_out, index=False)
    if args.json_out:
        payload = {
            "summary": result.to_dict(orient="records"),
            "folds": folds.to_dict(orient="records"),
            "universe": universe.to_dict(orient="records"),
        }
        Path(args.json_out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    command = "python cross_exchange_basis_report.py " + " ".join(
        token
        for token in [
            f"--exchanges {' '.join(args.exchanges)}",
            f"--days {args.days}",
            f"--min-quote-volume-usdt {args.min_quote_volume_usdt:g}",
            f"--max-symbols {args.max_symbols}",
            f"--train-samples {args.train_samples}",
            f"--test-samples {args.test_samples}",
            f"--min-folds {args.min_folds}",
        ]
        if token
    )
    if args.md_out:
        write_markdown(result, folds, universe, args.md_out, command=command, min_folds=args.min_folds)
    if args.json:
        print(json.dumps(result.to_dict(orient="records"), indent=2, sort_keys=True))
    else:
        print(result.to_string(index=False))
        if args.out:
            print(f"Output: {args.out}")
        if args.md_out:
            print(f"Markdown: {args.md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
