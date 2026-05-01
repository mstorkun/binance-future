from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd

import config
import portfolio_backtest as pb


def symbol_return_frame(data_by_symbol: dict[str, dict], symbols: list[str]) -> pd.DataFrame:
    rows = {}
    for symbol in symbols:
        df = data_by_symbol[symbol]["df"]
        rows[symbol] = pd.to_numeric(df["close"], errors="coerce").pct_change()
    frame = pd.DataFrame(rows).dropna(how="any")
    return frame


def pairwise_correlation_rows(returns: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for left, right in combinations(returns.columns, 2):
        corr = float(returns[left].corr(returns[right]))
        rows.append({
            "left": left,
            "right": right,
            "correlation": corr,
            "abs_correlation": abs(corr),
        })
    return sorted(rows, key=lambda row: row["abs_correlation"], reverse=True)


def stress_summary(returns: pd.DataFrame, *, high_corr_threshold: float = 0.85) -> dict[str, Any]:
    rows = pairwise_correlation_rows(returns)
    max_abs = max((row["abs_correlation"] for row in rows), default=0.0)
    avg_abs = sum(row["abs_correlation"] for row in rows) / len(rows) if rows else 0.0
    return {
        "symbols": list(returns.columns),
        "bars": int(len(returns)),
        "pair_count": int(len(rows)),
        "max_abs_correlation": max_abs,
        "avg_abs_correlation": avg_abs,
        "high_corr_threshold": high_corr_threshold,
        "high_corr_pairs": [row for row in rows if row["abs_correlation"] >= high_corr_threshold],
        "suggested_portfolio_risk_multiplier": suggested_risk_multiplier(max_abs),
        "pairs": rows,
    }


def suggested_risk_multiplier(max_abs_correlation: float) -> float:
    if max_abs_correlation >= 0.85:
        return 0.50
    if max_abs_correlation >= 0.70:
        return 0.75
    return 1.0


def run_correlation_stress(
    *,
    symbols: list[str] | None = None,
    years: int = 3,
    out_json: str = "correlation_stress_report.json",
    out_csv: str = "correlation_stress_pairs.csv",
) -> dict[str, Any]:
    symbols = symbols or list(config.SYMBOLS)
    data = pb.fetch_all_data(symbols, years=years)
    returns = symbol_return_frame(data, symbols)
    summary = stress_summary(returns)
    if out_json:
        Path(out_json).write_text(json.dumps(_clean(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if out_csv:
        pd.DataFrame(summary["pairs"]).to_csv(out_csv, index=False)
    return summary


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure portfolio symbol correlation stress.")
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--out-json", default="correlation_stress_report.json")
    parser.add_argument("--out-csv", default="correlation_stress_pairs.csv")
    args = parser.parse_args()

    summary = run_correlation_stress(
        symbols=args.symbols,
        years=args.years,
        out_json=args.out_json,
        out_csv=args.out_csv,
    )
    print(json.dumps(_clean({k: v for k, v in summary.items() if k != "pairs"}), indent=2, sort_keys=True))
    print(f"Output: {args.out_json}, {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
