from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

import candle_structure as cs
import config
import correlation_stress
import portfolio_backtest as pb


def _side_to_bias(side: str) -> int:
    return 1 if str(side).lower() == "long" else -1


def _signal_bar(df: pd.DataFrame, entry_time: pd.Timestamp) -> pd.Series | None:
    pos = df.index.searchsorted(entry_time)
    signal_pos = int(pos) - 1
    if signal_pos < 0 or signal_pos >= len(df):
        return None
    return df.iloc[signal_pos]


def annotate_trades(
    trades: pd.DataFrame,
    data_by_symbol: dict[str, dict],
    *,
    symbol_max_abs_corr: dict[str, float] | None = None,
) -> pd.DataFrame:
    symbol_max_abs_corr = symbol_max_abs_corr or {}
    frames = {
        symbol: cs.add_candle_structure_features(data["df"])
        for symbol, data in data_by_symbol.items()
    }
    rows: list[dict[str, Any]] = []
    for _, trade in trades.iterrows():
        symbol = str(trade["symbol"])
        df = frames.get(symbol)
        if df is None or df.empty:
            continue
        entry_time = pd.to_datetime(trade["entry_time"])
        bar = _signal_bar(df, entry_time)
        if bar is None:
            continue
        side_bias = _side_to_bias(str(trade["side"]))
        candle_bias = int(bar.get("candle_structure_bias", 0) or 0)
        if candle_bias == side_bias:
            alignment = "aligned"
        elif candle_bias == 0:
            alignment = "neutral"
        else:
            alignment = "contra"
        row = trade.to_dict()
        row.update({
            "signal_bar_time": bar.name,
            "candle_structure_bias": candle_bias,
            "candle_structure_alignment": alignment,
            "candle_structure_confidence": float(bar.get("candle_structure_confidence", 0.0) or 0.0),
            "candle_structure_score_long": float(bar.get("candle_structure_score_long", 0.0) or 0.0),
            "candle_structure_score_short": float(bar.get("candle_structure_score_short", 0.0) or 0.0),
            "candle_structure_reasons": str(bar.get("candle_structure_reasons", "") or ""),
            "candle_density": float(bar.get("candle_density", 0.0) or 0.0),
            "candle_compression": float(bar.get("candle_compression", 0.0) or 0.0),
            "candle_expansion": float(bar.get("candle_expansion", 0.0) or 0.0),
            "candle_direction_consistency": float(bar.get("candle_direction_consistency", 0.0) or 0.0),
            "candle_return_autocorr": float(bar.get("candle_return_autocorr", 0.0) or 0.0),
            "candle_range_volume_corr": float(bar.get("candle_range_volume_corr", 0.0) or 0.0),
            "symbol_max_abs_corr": float(symbol_max_abs_corr.get(symbol, 0.0)),
        })
        rows.append(row)
    return pd.DataFrame(rows)


def max_abs_corr_by_symbol(data_by_symbol: dict[str, dict], symbols: list[str]) -> dict[str, float]:
    returns = correlation_stress.symbol_return_frame(data_by_symbol, symbols)
    pairs = correlation_stress.pairwise_correlation_rows(returns)
    out = {symbol: 0.0 for symbol in symbols}
    for row in pairs:
        left = row["left"]
        right = row["right"]
        corr = float(row["abs_correlation"])
        out[left] = max(out.get(left, 0.0), corr)
        out[right] = max(out.get(right, 0.0), corr)
    return out


def profit_factor(pnl: pd.Series) -> float | None:
    wins = float(pnl[pnl > 0].sum())
    losses = abs(float(pnl[pnl < 0].sum()))
    if losses == 0:
        return None
    return wins / losses


def summarize_frame(name: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "segment": name,
            "trades": 0,
            "win_rate_pct": 0.0,
            "pnl": 0.0,
            "mean_return_pct": 0.0,
            "profit_factor": None,
            "avg_confidence": 0.0,
            "avg_density": 0.0,
            "avg_symbol_corr": 0.0,
        }
    pnl = pd.to_numeric(frame["pnl"], errors="coerce").fillna(0.0)
    returns = pd.to_numeric(frame.get("pnl_return_pct", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    pf = profit_factor(pnl)
    return {
        "segment": name,
        "trades": int(len(frame)),
        "win_rate_pct": round(float((pnl > 0).sum() / len(frame) * 100.0), 4),
        "pnl": round(float(pnl.sum()), 4),
        "mean_return_pct": round(float(returns.mean()), 4),
        "profit_factor": round(float(pf), 4) if pf is not None else None,
        "avg_confidence": round(float(pd.to_numeric(frame["candle_structure_confidence"], errors="coerce").mean()), 4),
        "avg_density": round(float(pd.to_numeric(frame["candle_density"], errors="coerce").mean()), 4),
        "avg_symbol_corr": round(float(pd.to_numeric(frame["symbol_max_abs_corr"], errors="coerce").mean()), 4),
    }


def summarize_by(frame: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    rows = [summarize_frame(str(name), part) for name, part in frame.groupby(column, dropna=False)]
    return sorted(rows, key=lambda row: (-int(row["trades"]), str(row["segment"])))


def build_report(annotated: pd.DataFrame) -> dict[str, Any]:
    if annotated.empty:
        return {"overall": summarize_frame("all", annotated), "by_alignment": [], "by_side": [], "by_symbol": []}
    return {
        "overall": summarize_frame("all", annotated),
        "by_alignment": summarize_by(annotated, "candle_structure_alignment"),
        "by_side": summarize_by(annotated, "side"),
        "by_symbol": summarize_by(annotated, "symbol"),
    }


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


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


def write_markdown(report: dict[str, Any], path: str | Path, *, source: str, years: int) -> None:
    columns = [
        "segment",
        "trades",
        "win_rate_pct",
        "pnl",
        "mean_return_pct",
        "profit_factor",
        "avg_confidence",
        "avg_density",
        "avg_symbol_corr",
    ]
    lines = [
        "# Candle Structure Report - 2026-05-04",
        "",
        "This is a report-only diagnostic. It tests whether candle length,",
        "density/compression, directional persistence, volume-range correlation,",
        "and symbol return correlation separate better and worse trades.",
        "",
        f"Source trades file: `{source}`",
        f"Historical data window: `{years}` years",
        "",
        "## Overall",
        "",
        markdown_table([report["overall"]], columns),
        "",
        "## Structure Alignment",
        "",
        markdown_table(report["by_alignment"], columns),
        "",
        "## Side",
        "",
        markdown_table(report["by_side"], columns),
        "",
        "## Symbol",
        "",
        markdown_table(report["by_symbol"], columns),
        "",
        "## Decision",
        "",
        "The candle-structure model is not an active trading rule. Promote it only",
        "after side-by-side backtest, walk-forward, and cost-stress results prove",
        "that it improves net return without hiding overfit.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_report(
    *,
    trades_path: str = "portfolio_trades.csv",
    symbols: list[str] | None = None,
    years: int = 3,
    json_out: str = "candle_structure_report.json",
    md_out: str = "docs/CANDLE_STRUCTURE_REPORT_2026_05_04.md",
) -> dict[str, Any]:
    symbols = symbols or list(config.SYMBOLS)
    trades = pd.read_csv(trades_path)
    data = pb.fetch_all_data(symbols, years=years)
    symbol_corr = max_abs_corr_by_symbol(data, symbols)
    annotated = annotate_trades(trades, data, symbol_max_abs_corr=symbol_corr)
    report = build_report(annotated)
    payload = {"symbol_max_abs_corr": symbol_corr, **report}
    if json_out:
        Path(json_out).write_text(json.dumps(_clean(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if md_out:
        write_markdown(payload, md_out, source=trades_path, years=years)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Report candle-structure attribution against trade results.")
    parser.add_argument("--trades", default="portfolio_trades.csv")
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--json-out", default="candle_structure_report.json")
    parser.add_argument("--md-out", default="docs/CANDLE_STRUCTURE_REPORT_2026_05_04.md")
    args = parser.parse_args()

    report = run_report(
        trades_path=args.trades,
        symbols=args.symbols,
        years=args.years,
        json_out=args.json_out,
        md_out=args.md_out,
    )
    print(json.dumps(_clean({k: v for k, v in report.items() if k != "by_symbol"}), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
