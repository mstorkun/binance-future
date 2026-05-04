from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import ccxt
import pandas as pd

import carry_research
import config


def funding_values(rates: pd.DataFrame) -> pd.Series:
    if rates.empty or "funding_rate" not in rates.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(rates["funding_rate"], errors="coerce").dropna().sort_index()


def future_sum(values: pd.Series, *, horizon: int = 3) -> pd.Series:
    horizon = max(1, int(horizon))
    out = pd.Series(0.0, index=values.index)
    for step in range(1, horizon + 1):
        out = out.add(values.shift(-step), fill_value=0.0)
    if len(out) <= horizon:
        return pd.Series(dtype=float)
    return out.iloc[:-horizon]


def prediction_frame(
    rates: pd.DataFrame,
    *,
    signal_window: int = 3,
    horizon: int = 3,
) -> pd.DataFrame:
    values = funding_values(rates)
    if values.empty:
        return pd.DataFrame(columns=["funding_rate", "signal", "future_sum"])
    signal_window = max(1, int(signal_window))
    frame = pd.DataFrame(
        {
            "funding_rate": values,
            # This uses only already observed funding prints at timestamp t.
            "signal": values.rolling(signal_window, min_periods=signal_window).mean(),
            "future_sum": future_sum(values, horizon=horizon),
        }
    )
    return frame.dropna().sort_index()


def evaluate_threshold_fold(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    symbol: str,
    fold: int,
    top_quantile: float = 0.8,
    min_selected: int = 10,
    horizon: int = 3,
) -> dict[str, Any]:
    top_quantile = min(max(float(top_quantile), 0.5), 0.99)
    if train.empty or test.empty:
        return {
            "symbol": symbol,
            "fold": int(fold),
            "ok": False,
            "reason": "empty_fold",
        }
    threshold = float(train["signal"].quantile(top_quantile))
    selected = test[test["signal"] >= threshold]
    baseline_mean = float(test["future_sum"].mean())
    selected_mean = float(selected["future_sum"].mean()) if not selected.empty else 0.0
    baseline_hit = float((test["future_sum"] > 0).mean() * 100.0)
    selected_hit = float((selected["future_sum"] > 0).mean() * 100.0) if not selected.empty else 0.0
    edge_pct = (selected_mean - baseline_mean) * 100.0
    selected_annualized_apr = selected_mean / max(1, int(horizon)) * carry_research.FUNDING_INTERVALS_PER_YEAR * 100.0
    baseline_annualized_apr = baseline_mean / max(1, int(horizon)) * carry_research.FUNDING_INTERVALS_PER_YEAR * 100.0
    train_corr = train["signal"].corr(train["future_sum"])
    test_corr = test["signal"].corr(test["future_sum"])
    ok = bool(len(selected) >= int(min_selected) and edge_pct > 0.0 and selected_hit >= baseline_hit)
    return {
        "symbol": symbol,
        "fold": int(fold),
        "train_start": train.index.min().isoformat(),
        "train_end": train.index.max().isoformat(),
        "test_start": test.index.min().isoformat(),
        "test_end": test.index.max().isoformat(),
        "train_samples": int(len(train)),
        "test_samples": int(len(test)),
        "selected_samples": int(len(selected)),
        "top_quantile": round(top_quantile, 4),
        "signal_threshold": round(threshold, 10),
        "baseline_future_sum_pct": round(baseline_mean * 100.0, 6),
        "selected_future_sum_pct": round(selected_mean * 100.0, 6),
        "edge_vs_baseline_pct": round(edge_pct, 6),
        "baseline_positive_future_pct": round(baseline_hit, 4),
        "selected_positive_future_pct": round(selected_hit, 4),
        "baseline_annualized_apr_pct": round(baseline_annualized_apr, 4),
        "selected_annualized_apr_pct": round(selected_annualized_apr, 4),
        "train_signal_future_corr": round(float(train_corr), 6) if pd.notna(train_corr) else 0.0,
        "test_signal_future_corr": round(float(test_corr), 6) if pd.notna(test_corr) else 0.0,
        "ok": ok,
        "reason": "" if ok else "no_oos_predictive_edge",
    }


def walk_forward_predictability(
    rates: pd.DataFrame,
    *,
    symbol: str,
    signal_window: int = 3,
    horizon: int = 3,
    top_quantile: float = 0.8,
    train_samples: int = 360,
    test_samples: int = 90,
    roll_samples: int = 90,
    min_selected: int = 10,
    min_folds: int = 3,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    frame = prediction_frame(rates, signal_window=signal_window, horizon=horizon)
    if frame.empty:
        return {
            "symbol": symbol,
            "samples": 0,
            "folds": 0,
            "ok": False,
            "reason": "no_prediction_frame",
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
        folds.append(
            evaluate_threshold_fold(
                train,
                test,
                symbol=symbol,
                fold=fold,
                top_quantile=top_quantile,
                min_selected=min_selected,
                horizon=horizon,
            )
        )
        if start + train_samples + test_samples >= len(frame):
            break
        start += roll_samples
        fold += 1

    if not folds:
        return {
            "symbol": symbol,
            "samples": int(len(frame)),
            "folds": 0,
            "ok": False,
            "reason": "insufficient_samples_for_walk_forward",
        }, []

    selected_samples = sum(int(row.get("selected_samples", 0) or 0) for row in folds)
    test_samples_total = sum(int(row.get("test_samples", 0) or 0) for row in folds)
    ok_folds = sum(1 for row in folds if row.get("ok"))
    weighted_edge = (
        sum(float(row.get("edge_vs_baseline_pct", 0.0) or 0.0) * int(row.get("selected_samples", 0) or 0) for row in folds)
        / max(selected_samples, 1)
    )
    avg_selected_apr = (
        sum(float(row.get("selected_annualized_apr_pct", 0.0) or 0.0) * int(row.get("selected_samples", 0) or 0) for row in folds)
        / max(selected_samples, 1)
    )
    avg_baseline_apr = (
        sum(float(row.get("baseline_annualized_apr_pct", 0.0) or 0.0) * int(row.get("test_samples", 0) or 0) for row in folds)
        / max(test_samples_total, 1)
    )
    summary = {
        "symbol": symbol,
        "samples": int(len(frame)),
        "folds": int(len(folds)),
        "ok_folds": int(ok_folds),
        "selected_samples": int(selected_samples),
        "test_samples": int(test_samples_total),
        "avg_edge_vs_baseline_pct": round(float(weighted_edge), 6),
        "avg_selected_annualized_apr_pct": round(float(avg_selected_apr), 4),
        "avg_baseline_annualized_apr_pct": round(float(avg_baseline_apr), 4),
        "ok": bool(
            len(folds) >= int(min_folds)
            and ok_folds == len(folds)
            and weighted_edge > 0.0
            and selected_samples >= int(min_selected) * len(folds)
        ),
        "reason": "",
    }
    if not summary["ok"]:
        summary["reason"] = (
            "insufficient_oos_folds" if len(folds) < int(min_folds) else "insufficient_oos_predictive_edge"
        )
    return summary, folds


def scan_symbols(
    symbols: list[str],
    *,
    days: int = 180,
    signal_window: int = 3,
    horizon: int = 3,
    top_quantile: float = 0.8,
    train_samples: int = 360,
    test_samples: int = 90,
    roll_samples: int = 90,
    min_selected: int = 10,
    min_folds: int = 3,
    exchange: ccxt.Exchange | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    exchange = exchange or ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    summaries: list[dict[str, Any]] = []
    folds: list[dict[str, Any]] = []
    for symbol in symbols:
        rates = carry_research.fetch_funding_history(exchange, symbol, days=days)
        summary, symbol_folds = walk_forward_predictability(
            rates,
            symbol=symbol,
            signal_window=signal_window,
            horizon=horizon,
            top_quantile=top_quantile,
            train_samples=train_samples,
            test_samples=test_samples,
            roll_samples=roll_samples,
            min_selected=min_selected,
            min_folds=min_folds,
        )
        summaries.append(summary)
        folds.extend(symbol_folds)
    result = pd.DataFrame(summaries)
    if not result.empty:
        result = result.sort_values(
            ["ok", "avg_edge_vs_baseline_pct", "avg_selected_annualized_apr_pct"],
            ascending=[False, False, False],
        ).reset_index(drop=True)
    return result, pd.DataFrame(folds)


def scan_auto_universe(
    *,
    days: int = 180,
    min_quote_volume_usdt: float = carry_research.DEFAULT_MIN_QUOTE_VOLUME_USDT,
    max_symbols: int = carry_research.DEFAULT_MAX_SYMBOLS,
    signal_window: int = 3,
    horizon: int = 3,
    top_quantile: float = 0.8,
    train_samples: int = 360,
    test_samples: int = 90,
    roll_samples: int = 90,
    min_selected: int = 10,
    min_folds: int = 3,
    ascii_only: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    spot_exchange = ccxt.binance({"enableRateLimit": True})
    universe = carry_research.discover_carry_universe(
        exchange,
        spot_exchange,
        min_quote_volume_usdt=min_quote_volume_usdt,
        max_symbols=max_symbols,
        ascii_only=ascii_only,
    )
    if universe.empty:
        return universe, pd.DataFrame(), pd.DataFrame()
    result, folds = scan_symbols(
        universe["symbol"].tolist(),
        days=days,
        signal_window=signal_window,
        horizon=horizon,
        top_quantile=top_quantile,
        train_samples=train_samples,
        test_samples=test_samples,
        roll_samples=roll_samples,
        min_selected=min_selected,
        min_folds=min_folds,
        exchange=exchange,
    )
    if not result.empty:
        result = result.merge(universe, on="symbol", how="left")
    return universe, result, folds


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
    path: str | Path,
    *,
    command: str,
    min_folds: int,
) -> None:
    pass_count = int(result["ok"].sum()) if "ok" in result.columns else 0
    rows = result.head(12).to_dict(orient="records") if not result.empty else []
    columns = [
        "symbol",
        "folds",
        "ok_folds",
        "selected_samples",
        "avg_edge_vs_baseline_pct",
        "avg_selected_annualized_apr_pct",
        "avg_baseline_annualized_apr_pct",
        "ok",
        "reason",
    ]
    lines = [
        "# Funding Predictability PoC - 2026-05-04",
        "",
        "This is a research-only prediction report. It does not create a carry",
        "executor, does not place orders, and does not change paper/testnet/live",
        "behavior.",
        "",
        "## Method",
        "",
        "For each symbol, the signal is the rolling mean of already observed funding",
        "prints. A threshold is learned on each train window; the test window then",
        "checks whether high-signal periods have better future funding than the",
        "unconditional test baseline.",
        "",
        f"Strict pass gate: at least `{min_folds}` OOS folds, every fold must pass,",
        "weighted OOS edge must be positive, and the selected sample count must meet",
        "the per-fold minimum.",
        "",
        f"Command: `{command}`",
        "",
        "## Result",
        "",
        f"- Symbols scanned: `{len(result)}`",
        f"- Passing symbols: `{pass_count}`",
        f"- Fold rows: `{len(folds)}`",
        "",
        markdown_table(rows, columns),
        "",
        "## Decision",
        "",
        "A pass here would not be live or executor approval; it would only mean a",
        "symbol deserves deeper research with costs, borrow/transfer constraints,",
        "liquidity, and walk-forward model stability. Pass count is zero under the",
        "strict gate, so do not build a funding executor from this PoC.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Research-only OOS funding predictability PoC.")
    parser.add_argument("--symbols", nargs="*", default=list(getattr(config, "SYMBOLS", [])))
    parser.add_argument("--auto-universe", action="store_true")
    parser.add_argument("--min-quote-volume-usdt", type=float, default=carry_research.DEFAULT_MIN_QUOTE_VOLUME_USDT)
    parser.add_argument("--max-symbols", type=int, default=carry_research.DEFAULT_MAX_SYMBOLS)
    parser.add_argument("--include-non-ascii", action="store_true")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--signal-window", type=int, default=3)
    parser.add_argument("--horizon", type=int, default=3)
    parser.add_argument("--top-quantile", type=float, default=0.8)
    parser.add_argument("--train-samples", type=int, default=360)
    parser.add_argument("--test-samples", type=int, default=90)
    parser.add_argument("--roll-samples", type=int, default=90)
    parser.add_argument("--min-selected", type=int, default=10)
    parser.add_argument("--min-folds", type=int, default=3)
    parser.add_argument("--out", default="funding_predictability_results.csv")
    parser.add_argument("--folds-out", default="funding_predictability_folds.csv")
    parser.add_argument("--universe-out", default="funding_predictability_universe.csv")
    parser.add_argument("--json-out", default="funding_predictability_report.json")
    parser.add_argument("--md-out", default="docs/FUNDING_PREDICTABILITY_2026_05_04.md")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.auto_universe:
        universe, result, folds = scan_auto_universe(
            days=args.days,
            min_quote_volume_usdt=args.min_quote_volume_usdt,
            max_symbols=args.max_symbols,
            signal_window=args.signal_window,
            horizon=args.horizon,
            top_quantile=args.top_quantile,
            train_samples=args.train_samples,
            test_samples=args.test_samples,
            roll_samples=args.roll_samples,
            min_selected=args.min_selected,
            min_folds=args.min_folds,
            ascii_only=not args.include_non_ascii,
        )
        if args.universe_out:
            universe.to_csv(args.universe_out, index=False)
    else:
        result, folds = scan_symbols(
            args.symbols,
            days=args.days,
            signal_window=args.signal_window,
            horizon=args.horizon,
            top_quantile=args.top_quantile,
            train_samples=args.train_samples,
            test_samples=args.test_samples,
            roll_samples=args.roll_samples,
            min_selected=args.min_selected,
            min_folds=args.min_folds,
        )

    if args.out:
        result.to_csv(args.out, index=False)
    if args.folds_out:
        folds.to_csv(args.folds_out, index=False)
    if args.json_out:
        payload = {"summary": result.to_dict(orient="records"), "folds": folds.to_dict(orient="records")}
        Path(args.json_out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    command = "python funding_predictability_report.py " + " ".join(
        token
        for token in [
            "--auto-universe" if args.auto_universe else "",
            f"--days {args.days}",
            f"--signal-window {args.signal_window}",
            f"--horizon {args.horizon}",
            f"--top-quantile {args.top_quantile:g}",
            f"--train-samples {args.train_samples}",
            f"--test-samples {args.test_samples}",
            f"--min-folds {args.min_folds}",
        ]
        if token
    )
    if args.md_out:
        write_markdown(result, folds, args.md_out, command=command, min_folds=args.min_folds)
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
