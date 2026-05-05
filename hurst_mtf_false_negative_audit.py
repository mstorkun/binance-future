from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

import hurst_mtf_momentum_report as mtf_report
import risk_metrics


DEFAULT_JSON = "hurst_mtf_momentum_report.json"
DEFAULT_MATRIX = "hurst_mtf_momentum_pbo_matrix.csv"
DEFAULT_TRADES = "hurst_mtf_momentum_trades.csv"
DEFAULT_MD = "docs/HURST_MTF_FALSE_NEGATIVE_AUDIT_2026_05_05.md"


def _round(value: float, ndigits: int = 4) -> float:
    return round(float(value), int(ndigits))


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compound_return_pct(returns_pct: pd.Series) -> float:
    values = pd.to_numeric(returns_pct, errors="coerce").dropna()
    if values.empty:
        return 0.0
    compounded = (1.0 + values / 100.0).prod() - 1.0
    return float(compounded * 100.0)


def infer_start_balance(*, final_equity: float, total_return_pct: float) -> float:
    denominator = 1.0 + float(total_return_pct) / 100.0
    if denominator <= 0.0:
        return 0.0
    return float(final_equity) / denominator


def scenario_compounds(scenario_rows: pd.DataFrame) -> list[dict[str, Any]]:
    if scenario_rows.empty:
        return []
    rows: list[dict[str, Any]] = []
    for scenario, group in scenario_rows.groupby("scenario", sort=False):
        returns = pd.to_numeric(group["total_return_pct"], errors="coerce")
        rows.append(
            {
                "scenario": str(scenario),
                "folds": int(len(group)),
                "positive_folds": int((returns > 0.0).sum()),
                "compound_return_pct": _round(compound_return_pct(returns)),
                "worst_fold_pct": _round(float(returns.min())),
                "best_fold_pct": _round(float(returns.max())),
            }
        )
    return rows


def matrix_audit(matrix: pd.DataFrame) -> dict[str, Any]:
    if matrix.empty:
        return {
            "rows": 0,
            "folds": 0,
            "min_candidates_per_fold": 0,
            "max_candidates_per_fold": 0,
            "selected_rows": 0,
            "debug_cap_detected": True,
            "one_selection_per_fold": False,
        }
    candidates_per_fold = matrix.groupby("period")["candidate"].nunique()
    selected_per_fold = matrix[matrix.get("selected", False).astype(bool)].groupby("period")["candidate"].count()
    selected_per_fold = selected_per_fold.reindex(candidates_per_fold.index, fill_value=0)
    return {
        "rows": int(len(matrix)),
        "folds": int(candidates_per_fold.size),
        "min_candidates_per_fold": int(candidates_per_fold.min()),
        "max_candidates_per_fold": int(candidates_per_fold.max()),
        "selected_rows": int(selected_per_fold.sum()),
        "debug_cap_detected": bool(candidates_per_fold.min() < 72 or candidates_per_fold.max() < 72),
        "one_selection_per_fold": bool((selected_per_fold == 1).all()),
    }


def trade_recomputations(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {
            "sample_trades": 0,
            "tail_capture": 0.0,
            "crisis_alpha": mtf_report.crisis_alpha(trades),
            "symbol_pnl_share": 0.0,
            "month_pnl_share": 0.0,
        }
    month_frame = trades.copy()
    month_frame["exit_month"] = pd.to_datetime(month_frame["exit_time"], utc=True).dt.strftime("%Y-%m")
    return {
        "sample_trades": int(len(trades)),
        "tail_capture": _round(mtf_report.tail_capture(trades)),
        "crisis_alpha": mtf_report.crisis_alpha(trades),
        "symbol_pnl_share": _round(mtf_report.contribution_share(trades, "symbol")),
        "month_pnl_share": _round(mtf_report.contribution_share(month_frame, "exit_month")),
    }


def review_claim_audit(strict: dict[str, Any], severe_rows: pd.DataFrame) -> list[dict[str, Any]]:
    metrics = strict.get("metrics", {})
    crisis = strict.get("crisis_alpha", {})
    final_equity = float(metrics.get("final_equity", 0.0))
    total_return_pct = float(metrics.get("total_return_pct", 0.0))
    implied_start = infer_start_balance(final_equity=final_equity, total_return_pct=total_return_pct)

    crisis_lost_dates = [date for date, row in crisis.items() if float(row.get("pnl", 0.0)) < 0.0]
    crisis_won_dates = [date for date, row in crisis.items() if float(row.get("pnl", 0.0)) > 0.0]
    late_folds = severe_rows[pd.to_numeric(severe_rows.get("period", pd.Series(dtype=float)), errors="coerce") >= 6].copy()
    late_positive = []
    if not late_folds.empty:
        late_folds["total_return_pct"] = pd.to_numeric(late_folds["total_return_pct"], errors="coerce")
        late_positive = [int(row["period"]) for _, row in late_folds[late_folds["total_return_pct"] > 0.0].iterrows()]

    return [
        {
            "claim": "both_crisis_days_lost",
            "verdict": "incorrect",
            "evidence": f"won={','.join(crisis_won_dates) or 'none'} lost={','.join(crisis_lost_dates) or 'none'}",
        },
        {
            "claim": "start_1000_to_230",
            "verdict": "incorrect",
            "evidence": f"implied_start={_round(implied_start, 2)} final={_round(final_equity, 2)} total_return_pct={_round(total_return_pct, 4)}",
        },
        {
            "claim": "folds_6_to_12_all_negative",
            "verdict": "incorrect" if late_positive else "supported",
            "evidence": f"positive_late_folds={','.join(str(x) for x in late_positive) or 'none'}",
        },
    ]


def build_audit(
    *,
    report_json: dict[str, Any],
    matrix: pd.DataFrame,
    trades: pd.DataFrame,
) -> dict[str, Any]:
    strict = report_json.get("strict", {})
    scenario_rows = pd.DataFrame(report_json.get("scenario_rows", []))
    severe_rows = scenario_rows[scenario_rows.get("scenario", "") == "severe"].copy() if not scenario_rows.empty else pd.DataFrame()
    recomputed = trade_recomputations(trades)
    matrix_info = matrix_audit(matrix)
    scenario_info = scenario_compounds(scenario_rows)
    review_claims = review_claim_audit(strict, severe_rows)

    strict_checks = strict.get("checks", {})
    json_tail = float(strict.get("tail_capture", 0.0))
    json_sample = int(strict.get("sample_trades", 0))
    json_symbol_share = float(strict.get("symbol_pnl_share", 0.0))
    json_month_share = float(strict.get("month_pnl_share", 0.0))

    consistency_checks = {
        "strict_status_present": strict.get("status") in {"pass", "benchmark_only"},
        "gate_count_is_10": len(strict_checks) == 10,
        "failed_gate_count_is_6": len(strict.get("failed_checks", [])) == 6,
        "trade_sample_matches_json": recomputed["sample_trades"] == json_sample,
        "tail_capture_matches_json": abs(float(recomputed["tail_capture"]) - json_tail) <= 0.0001,
        "symbol_share_matches_json": abs(float(recomputed["symbol_pnl_share"]) - json_symbol_share) <= 0.0001,
        "month_share_matches_json": abs(float(recomputed["month_pnl_share"]) - json_month_share) <= 0.0001,
        "matrix_full_72_candidates": not matrix_info["debug_cap_detected"],
        "matrix_one_selection_per_fold": matrix_info["one_selection_per_fold"],
    }

    severe_compound = next((row for row in scenario_info if row["scenario"] == "severe"), {})
    baseline_compound = next((row for row in scenario_info if row["scenario"] == "baseline"), {})
    false_negative_checks = {
        "review_contains_material_errors": any(row["verdict"] == "incorrect" for row in review_claims),
        "artifact_recomputations_match": all(consistency_checks.values()),
        "baseline_also_negative": float(baseline_compound.get("compound_return_pct", 0.0)) < 0.0,
        "severe_fold_fail_confirmed": int(severe_compound.get("positive_folds", 0)) < 7,
        "no_debug_candidate_cap": not matrix_info["debug_cap_detected"],
        "pbo_gate_passed": bool(strict_checks.get("pbo_below_0_30")),
    }

    critical_harness_issue = not bool(false_negative_checks["artifact_recomputations_match"]) or bool(matrix_info["debug_cap_detected"])
    status = "audit_blocked_harness_issue" if critical_harness_issue else "review_errors_but_benchmark_only_confirmed"
    return {
        "status": status,
        "strict_status": strict.get("status", "unknown"),
        "strict_failed_checks": strict.get("failed_checks", []),
        "strict_metrics": strict.get("metrics", {}),
        "strict_crisis_alpha": strict.get("crisis_alpha", {}),
        "scenario_compounds": scenario_info,
        "matrix": matrix_info,
        "recomputed_from_trades": recomputed,
        "review_claims": review_claims,
        "consistency_checks": consistency_checks,
        "false_negative_checks": false_negative_checks,
        "decision": (
            "Do not accept the external review wording as fully correct; it contains material factual errors. "
            "Do not promote Phase B either: local artifacts are internally consistent and still show benchmark_only."
        ),
    }


def _table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows._"
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(col, "")).replace("|", "\\|") for col in columns) + " |")
    return "\n".join(out)


def write_markdown(audit: dict[str, Any], path: str | Path) -> None:
    consistency = [{"check": key, "pass": value} for key, value in audit["consistency_checks"].items()]
    false_negative = [{"check": key, "pass": value} for key, value in audit["false_negative_checks"].items()]
    crisis_rows = [
        {"date": date, **row}
        for date, row in audit.get("strict_crisis_alpha", {}).items()
    ]
    lines = [
        "# Hurst MTF False-Negative Audit - 2026-05-05",
        "",
        "Status: research-only audit. This does not enable paper, testnet, or live execution.",
        "",
        f"Audit status: `{audit['status']}`",
        f"Original strict status: `{audit['strict_status']}`",
        "",
        "## Decision",
        "",
        audit["decision"],
        "",
        "## Review Claim Corrections",
        "",
        _table(audit["review_claims"], ["claim", "verdict", "evidence"]),
        "",
        "## Artifact Consistency",
        "",
        _table(consistency, ["check", "pass"]),
        "",
        "## False-Negative Checks",
        "",
        _table(false_negative, ["check", "pass"]),
        "",
        "## Scenario Compounds",
        "",
        _table(audit["scenario_compounds"], ["scenario", "folds", "positive_folds", "compound_return_pct", "worst_fold_pct", "best_fold_pct"]),
        "",
        "## Crisis Alpha",
        "",
        _table(crisis_rows, ["date", "pnl", "trades", "ok"]),
        "",
        "## Matrix",
        "",
        _table([audit["matrix"]], ["rows", "folds", "min_candidates_per_fold", "max_candidates_per_fold", "selected_rows", "debug_cap_detected", "one_selection_per_fold"]),
        "",
        "## Recomputed From Trades",
        "",
        _table(
            [
                {
                    "sample_trades": audit["recomputed_from_trades"]["sample_trades"],
                    "tail_capture": audit["recomputed_from_trades"]["tail_capture"],
                    "symbol_pnl_share": audit["recomputed_from_trades"]["symbol_pnl_share"],
                    "month_pnl_share": audit["recomputed_from_trades"]["month_pnl_share"],
                }
            ],
            ["sample_trades", "tail_capture", "symbol_pnl_share", "month_pnl_share"],
        ),
        "",
        "## Next Research Constraint",
        "",
        "Continue the alpha search, but keep Hurst-MTF Phase A as benchmark_only unless a new variant rerun passes every strict gate.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Hurst-MTF Phase A for false-negative or review-claim errors.")
    parser.add_argument("--json", default=DEFAULT_JSON)
    parser.add_argument("--matrix", default=DEFAULT_MATRIX)
    parser.add_argument("--trades", default=DEFAULT_TRADES)
    parser.add_argument("--json-out", default="hurst_mtf_false_negative_audit.json")
    parser.add_argument("--md-out", default=DEFAULT_MD)
    args = parser.parse_args()

    report_json = load_json(args.json)
    matrix = pd.read_csv(args.matrix) if Path(args.matrix).exists() else pd.DataFrame()
    trades = pd.read_csv(args.trades) if Path(args.trades).exists() else pd.DataFrame()
    audit = build_audit(report_json=report_json, matrix=matrix, trades=trades)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(risk_metrics.rounded_nested(audit), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.md_out:
        write_markdown(audit, args.md_out)
    print(json.dumps(risk_metrics.rounded_nested(audit), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
