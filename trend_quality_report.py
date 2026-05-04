from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


POSITIVE_REASON_WEIGHTS = {
    "market:trend": 2,
    "adx:strong": 2,
    "adx:trend": 1,
    "daily:aligned": 1,
    "weekly:aligned": 1,
    "obv:aligned": 1,
    "pattern:aligned": 1,
    "pattern:strong_aligned": 2,
    "flow:taker_aligned": 1,
    "flow:top_aligned": 1,
    "flow:oi_aligned": 1,
    "vp:long_above_value": 1,
    "vp:short_below_value": 1,
}

NEGATIVE_REASON_WEIGHTS = {
    "market:range": -2,
    "adx:weak": -1,
    "adx:very_weak": -2,
    "daily:against": -2,
    "weekly:against": -1,
    "obv:against": -1,
    "pattern:contra": -1,
    "pattern:strong_contra": -2,
    "flow:crowded": -1,
    "flow:taker_contra": -1,
    "flow:top_contra": -1,
    "flow:oi_contra": -1,
    "flow:funding_expensive": -1,
    "flow:funding_extreme": -2,
    "vol:elevated": -1,
    "vol:high": -2,
    "vol:extreme": -3,
    "rsi:hot_long": -1,
    "rsi:cold_short": -1,
}


def reason_tokens(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    text = str(value)
    if not text or text.lower() == "nan":
        return ()
    return tuple(token.strip() for token in text.split("|") if token.strip())


def trend_quality_score(tokens: tuple[str, ...] | list[str]) -> int:
    score = 0
    for token in tokens:
        score += POSITIVE_REASON_WEIGHTS.get(token, 0)
        score += NEGATIVE_REASON_WEIGHTS.get(token, 0)
    return score


def trend_quality_bucket(score: int) -> str:
    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def annotate_trades(trades: pd.DataFrame) -> pd.DataFrame:
    out = trades.copy()
    if "risk_reasons" not in out.columns:
        out["risk_reasons"] = ""
    out["reason_tokens"] = out["risk_reasons"].apply(reason_tokens)
    out["trend_quality_score"] = out["reason_tokens"].apply(trend_quality_score)
    out["trend_quality_bucket"] = out["trend_quality_score"].apply(trend_quality_bucket)
    out["has_market_trend"] = out["reason_tokens"].apply(lambda tokens: "market:trend" in tokens)
    out["has_adx_strong"] = out["reason_tokens"].apply(lambda tokens: "adx:strong" in tokens)
    out["has_adx_trend"] = out["reason_tokens"].apply(
        lambda tokens: "adx:strong" in tokens or "adx:trend" in tokens
    )
    out["has_contra_context"] = out["reason_tokens"].apply(
        lambda tokens: any("contra" in token or token in {"flow:crowded", "market:range"} for token in tokens)
    )
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
            "mean_pnl": 0.0,
            "mean_return_pct": 0.0,
            "profit_factor": None,
            "avg_bars_held": 0.0,
        }
    pnl = pd.to_numeric(frame["pnl"], errors="coerce").fillna(0.0)
    returns = pd.to_numeric(frame.get("pnl_return_pct", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    bars = pd.to_numeric(frame.get("bars_held", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    pf = profit_factor(pnl)
    return {
        "segment": name,
        "trades": int(len(frame)),
        "win_rate_pct": round(float((pnl > 0).sum() / len(frame) * 100.0), 4),
        "pnl": round(float(pnl.sum()), 4),
        "mean_pnl": round(float(pnl.mean()), 4),
        "mean_return_pct": round(float(returns.mean()), 4),
        "profit_factor": round(float(pf), 4) if pf is not None and math.isfinite(pf) else None,
        "avg_bars_held": round(float(bars.mean()), 4),
    }


def summarize_by(annotated: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    rows = [summarize_frame(str(name), frame) for name, frame in annotated.groupby(column, dropna=False)]
    return sorted(rows, key=lambda row: (-int(row["trades"]), str(row["segment"])))


def summarize_tokens(annotated: pd.DataFrame, min_trades: int = 10) -> list[dict[str, Any]]:
    token_rows: list[dict[str, Any]] = []
    all_tokens = sorted({token for tokens in annotated["reason_tokens"] for token in tokens})
    for token in all_tokens:
        frame = annotated[annotated["reason_tokens"].apply(lambda tokens, t=token: t in tokens)]
        if len(frame) < min_trades:
            continue
        row = summarize_frame(token, frame)
        row["coverage_pct"] = round(float(len(frame) / len(annotated) * 100.0), 4) if len(annotated) else 0.0
        token_rows.append(row)
    return sorted(token_rows, key=lambda row: (float(row["pnl"]), int(row["trades"])), reverse=True)


def build_report(trades: pd.DataFrame, *, min_token_trades: int = 10) -> dict[str, Any]:
    annotated = annotate_trades(trades)
    by_bucket = summarize_by(annotated, "trend_quality_bucket")
    bucket_order = {"high": 0, "medium": 1, "low": 2}
    by_bucket = sorted(by_bucket, key=lambda row: bucket_order.get(str(row["segment"]), 99))
    return {
        "overall": summarize_frame("all", annotated),
        "by_quality_bucket": by_bucket,
        "by_side": summarize_by(annotated, "side") if "side" in annotated.columns else [],
        "by_exit_reason": summarize_by(annotated, "exit_reason") if "exit_reason" in annotated.columns else [],
        "by_reason_token": summarize_tokens(annotated, min_trades=min_token_trades),
    }


def _format_number(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows._"
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for row in rows:
        lines.append("| " + " | ".join(_format_number(row.get(col)) for col in columns) + " |")
    return "\n".join(lines)


def write_markdown(report: dict[str, Any], path: str | Path, *, source: str) -> None:
    columns = ["segment", "trades", "win_rate_pct", "pnl", "mean_return_pct", "profit_factor", "avg_bars_held"]
    token_columns = columns + ["coverage_pct"]
    lines = [
        "# Trend Quality Report - 2026-05-04",
        "",
        "This is a report-only diagnostic. It does not change entry, exit, sizing,",
        "paper trading, testnet, or live behavior.",
        "",
        f"Source trades file: `{source}`",
        "",
        "## Overall",
        "",
        markdown_table([report["overall"]], columns),
        "",
        "## Quality Buckets",
        "",
        markdown_table(report["by_quality_bucket"], columns),
        "",
        "## Side",
        "",
        markdown_table(report["by_side"], columns),
        "",
        "## Exit Reason",
        "",
        markdown_table(report["by_exit_reason"], columns),
        "",
        "## Reason Tokens",
        "",
        "Only tokens with enough observations are shown.",
        "",
        markdown_table(report["by_reason_token"], token_columns),
        "",
        "## Decision",
        "",
        "Long/short capability does not remove the need for trend quality. The",
        "system should keep measuring whether strong-trend context actually pays",
        "for whipsaws, fees, slippage, and funding before any filter is promoted",
        "from report-only to active trading behavior.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Report trend-quality attribution from trade CSV.")
    parser.add_argument("--trades", default="portfolio_trades.csv")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--md-out", default="")
    parser.add_argument("--min-token-trades", type=int, default=10)
    args = parser.parse_args()

    trades = pd.read_csv(args.trades)
    report = build_report(trades, min_token_trades=args.min_token_trades)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.md_out:
        write_markdown(report, args.md_out, source=args.trades)
    if not args.json_out and not args.md_out:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
