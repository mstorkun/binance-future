from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


def build_pbo_report(
    matrix: pd.DataFrame,
    *,
    train_metric: str = "train_score",
    test_metric: str = "test_return_pct",
) -> dict[str, Any]:
    if matrix.empty:
        return {"folds": 0, "warning": "empty_matrix"}
    required = {"period", "candidate", train_metric, test_metric}
    missing = sorted(required - set(matrix.columns))
    if missing:
        raise ValueError(f"missing matrix column(s): {', '.join(missing)}")

    rows: list[dict[str, Any]] = []
    for period, group in matrix.groupby("period", sort=True):
        group = group.copy()
        group[train_metric] = pd.to_numeric(group[train_metric], errors="coerce")
        group[test_metric] = pd.to_numeric(group[test_metric], errors="coerce")
        group = group.dropna(subset=[train_metric, test_metric])
        if group.empty:
            continue

        selected_rows = group[group.get("selected", False).astype(bool)] if "selected" in group else pd.DataFrame()
        if selected_rows.empty:
            selected = group.sort_values(train_metric, ascending=False).iloc[0]
        else:
            selected = selected_rows.iloc[0]

        test_ranked = group.sort_values(test_metric, ascending=False).reset_index(drop=True)
        selected_idx = test_ranked.index[test_ranked["candidate"] == selected["candidate"]]
        if len(selected_idx) == 0:
            continue
        test_rank = int(selected_idx[0]) + 1
        candidate_count = int(len(test_ranked))
        if candidate_count <= 1:
            oos_rank_pct = 1.0
        else:
            oos_rank_pct = 1.0 - ((test_rank - 1) / (candidate_count - 1))
        rows.append({
            "period": int(period),
            "candidate": str(selected["candidate"]),
            "candidate_count": candidate_count,
            "train_metric": float(selected[train_metric]),
            "test_metric": float(selected[test_metric]),
            "test_rank": test_rank,
            "oos_rank_pct": float(oos_rank_pct),
            "logit_oos_rank": _logit(oos_rank_pct),
            "pbo_hit": bool(oos_rank_pct < 0.5),
        })

    if not rows:
        return {"folds": 0, "warning": "no_valid_folds"}

    pbo = sum(1 for row in rows if row["pbo_hit"]) / len(rows)
    return {
        "folds": len(rows),
        "train_metric": train_metric,
        "test_metric": test_metric,
        "pbo": pbo,
        "avg_oos_rank_pct": sum(row["oos_rank_pct"] for row in rows) / len(rows),
        "median_oos_rank_pct": float(pd.Series([row["oos_rank_pct"] for row in rows]).median()),
        "selected": rows,
        "warning": "requires_full_candidate_by_fold_matrix",
    }


def _logit(value: float) -> float:
    clipped = min(max(float(value), 1e-12), 1.0 - 1e-12)
    return math.log(clipped / (1.0 - clipped))


def rounded_nested(value: Any, digits: int = 4) -> Any:
    if isinstance(value, dict):
        return {key: rounded_nested(item, digits=digits) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded_nested(item, digits=digits) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, digits)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a PBO-style report from a candidate-by-fold matrix.")
    parser.add_argument("--matrix", default="portfolio_param_candidate_matrix.csv")
    parser.add_argument("--train-metric", default="train_score")
    parser.add_argument("--test-metric", default="test_return_pct")
    parser.add_argument("--out", default="pbo_report.json")
    args = parser.parse_args()

    matrix = pd.read_csv(args.matrix)
    report = rounded_nested(build_pbo_report(matrix, train_metric=args.train_metric, test_metric=args.test_metric))
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
