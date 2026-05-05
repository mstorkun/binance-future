from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

import hurst_mtf_false_negative_audit as false_negative_audit
import risk_metrics


DEFAULT_TRADES = "hurst_mtf_momentum_trades.csv"
DEFAULT_RESULTS = "hurst_mtf_momentum_results.csv"
DEFAULT_MD = "docs/HURST_MTF_TRADE_DIAGNOSTICS_2026_05_05.md"


def _round(value: float, ndigits: int = 4) -> float:
    return round(float(value), int(ndigits))


def _safe_win_rate(pnl: pd.Series) -> float:
    clean = pd.to_numeric(pnl, errors="coerce").dropna()
    return float((clean > 0.0).mean()) if len(clean) else 0.0


def profit_factor(pnl: pd.Series) -> float:
    clean = pd.to_numeric(pnl, errors="coerce").dropna()
    profit = float(clean[clean > 0.0].sum())
    loss = abs(float(clean[clean < 0.0].sum()))
    if loss <= 0.0:
        return profit if profit > 0.0 else 0.0
    return float(profit / loss)


def summarize_by(trades: pd.DataFrame, columns: list[str], *, limit: int | None = None) -> list[dict[str, Any]]:
    if trades.empty or "pnl" not in trades:
        return []
    frame = trades.copy()
    frame["pnl"] = pd.to_numeric(frame["pnl"], errors="coerce")
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(columns, dropna=False, sort=True):
        if not isinstance(key, tuple):
            key = (key,)
        pnl = pd.to_numeric(group["pnl"], errors="coerce")
        row = {column: value for column, value in zip(columns, key)}
        row.update(
            {
                "trades": int(len(group)),
                "pnl": _round(float(pnl.sum())),
                "avg_pnl": _round(float(pnl.mean())),
                "win_rate": _round(_safe_win_rate(pnl)),
                "profit_factor": _round(profit_factor(pnl)),
            }
        )
        rows.append(row)
    rows.sort(key=lambda item: float(item["pnl"]))
    if limit is not None:
        rows = rows[: int(limit)]
    return rows


def scenario_compounds(results: pd.DataFrame) -> list[dict[str, Any]]:
    if results.empty:
        return []
    rows: list[dict[str, Any]] = []
    for scenario, group in results.groupby("scenario", sort=False):
        returns = pd.to_numeric(group["total_return_pct"], errors="coerce")
        rows.append(
            {
                "scenario": str(scenario),
                "folds": int(len(group)),
                "positive_folds": int((returns > 0.0).sum()),
                "compound_return_pct": _round(false_negative_audit.compound_return_pct(returns)),
                "worst_fold_pct": _round(float(returns.min())),
                "best_fold_pct": _round(float(returns.max())),
            }
        )
    return rows


def reentry_diagnostics(trades: pd.DataFrame, *, max_gap_hours: float = 24.0) -> dict[str, Any]:
    if trades.empty:
        return {
            "all_reentries": [],
            "after_losing_exits": [],
            "after_winning_trailing": [],
            "cooldown_hypothesis": {},
        }
    frame = trades.copy()
    frame["entry_time"] = pd.to_datetime(frame["entry_time"], utc=True)
    frame["exit_time"] = pd.to_datetime(frame["exit_time"], utc=True)
    frame["pnl"] = pd.to_numeric(frame["pnl"], errors="coerce")
    frame = frame.sort_values(["symbol", "entry_time"])

    rows: list[dict[str, Any]] = []
    for symbol, group in frame.groupby("symbol", sort=True):
        previous = None
        for _, current in group.iterrows():
            if previous is not None:
                gap = (current["entry_time"] - previous["exit_time"]).total_seconds() / 3600.0
                if 0.0 <= gap <= float(max_gap_hours):
                    rows.append(
                        {
                            "symbol": symbol,
                            "gap_hours": gap,
                            "side": current["side"],
                            "prev_side": previous["side"],
                            "prev_reason": previous["exit_reason"],
                            "prev_pnl": float(previous["pnl"]),
                            "pnl": float(current["pnl"]),
                        }
                    )
            previous = current
    reentries = pd.DataFrame(rows)
    if reentries.empty:
        return {
            "all_reentries": [],
            "after_losing_exits": [],
            "after_winning_trailing": [],
            "cooldown_hypothesis": {},
        }

    summary_rows: list[dict[str, Any]] = []
    for hours in (0.0, 4.0, 8.0, 12.0, 24.0):
        subset = reentries[reentries["gap_hours"] <= hours]
        pnl = pd.to_numeric(subset.get("pnl", pd.Series(dtype=float)), errors="coerce")
        summary_rows.append(
            {
                "gap_hours_lte": _round(hours, 1),
                "trades": int(len(subset)),
                "pnl": _round(float(pnl.sum()) if len(pnl) else 0.0),
                "avg_pnl": _round(float(pnl.mean()) if len(pnl) else 0.0),
                "win_rate": _round(_safe_win_rate(pnl)),
            }
        )

    losing_exit_reasons = {"hard_stop", "time_stop", "regime_exit"}
    after_loss = reentries[(reentries["prev_pnl"] < 0.0) & (reentries["prev_reason"].isin(losing_exit_reasons))].copy()
    after_winner = reentries[(reentries["prev_pnl"] > 0.0) & (reentries["prev_reason"] == "trailing_stop")].copy()
    after_loss_summary = summarize_by(after_loss, ["prev_reason", "side"]) if not after_loss.empty else []
    after_winner_summary = summarize_by(after_winner, ["side"]) if not after_winner.empty else []
    after_loss_pnl = float(pd.to_numeric(after_loss.get("pnl", pd.Series(dtype=float)), errors="coerce").sum()) if not after_loss.empty else 0.0
    after_winner_pnl = float(pd.to_numeric(after_winner.get("pnl", pd.Series(dtype=float)), errors="coerce").sum()) if not after_winner.empty else 0.0

    return {
        "all_reentries": summary_rows,
        "after_losing_exits": after_loss_summary,
        "after_winning_trailing": after_winner_summary,
        "cooldown_hypothesis": {
            "losing_exit_reentry_trades": int(len(after_loss)),
            "losing_exit_reentry_pnl": _round(after_loss_pnl),
            "winning_trailing_reentry_trades": int(len(after_winner)),
            "winning_trailing_reentry_pnl": _round(after_winner_pnl),
            "next_variant": "block same-symbol reentry for 24h after losing hard_stop/time_stop/regime_exit; do not block after profitable trailing_stop",
        },
    }


def top_trades(trades: pd.DataFrame, *, n: int = 10, winners: bool = True) -> list[dict[str, Any]]:
    if trades.empty:
        return []
    frame = trades.copy()
    frame["pnl"] = pd.to_numeric(frame["pnl"], errors="coerce")
    cols = ["period", "symbol", "side", "entry_time", "exit_time", "exit_reason", "pnl", "bars_held", "reached_1r"]
    picked = frame.nlargest(n, "pnl") if winners else frame.nsmallest(n, "pnl")
    return picked[cols].to_dict(orient="records")


def build_diagnostics(trades: pd.DataFrame, results: pd.DataFrame, *, family_limit_reached: bool = False) -> dict[str, Any]:
    by_exit_reason = summarize_by(trades, ["exit_reason"])
    by_side = summarize_by(trades, ["side"])
    by_symbol = summarize_by(trades, ["symbol"])
    by_period = summarize_by(trades, ["period"])
    by_side_exit = summarize_by(trades, ["side", "exit_reason"])
    reentries = reentry_diagnostics(trades)
    scenarios = scenario_compounds(results)
    cooldown_numbers = dict(reentries.get("cooldown_hypothesis", {}))
    cooldown_numbers.pop("next_variant", None)

    hard_stop = next((row for row in by_exit_reason if row.get("exit_reason") == "hard_stop"), {})
    trailing_stop = next((row for row in by_exit_reason if row.get("exit_reason") == "trailing_stop"), {})
    severe = next((row for row in scenarios if row.get("scenario") == "severe"), {})
    baseline = next((row for row in scenarios if row.get("scenario") == "baseline"), {})
    baseline_return = float(baseline.get("compound_return_pct", 0.0))
    severe_return = float(severe.get("compound_return_pct", 0.0))
    cooldown_leak = float(reentries.get("cooldown_hypothesis", {}).get("losing_exit_reentry_pnl", 0.0))
    if family_limit_reached and severe_return < 0.0:
        next_candidate = {
            "name": "LEAVE_HURST_MTF_FAMILY",
            "scope": "V3 was the planned cost-robust follow-up and still failed strict gates; stop adding filters to this family and test a different alpha family.",
            "live_validation": "Do not micro-live this family unless a future independent candidate first passes strict research gates.",
        }
    elif cooldown_leak < -1000.0:
        next_candidate = {
            "name": "HURST_MTF_COOLDOWN_V2",
            "scope": "Add 24h same-symbol cooldown only after losing hard_stop/time_stop/regime_exit; keep trailing winners unrestricted; rerun full strict gate.",
            "live_validation": "If a future variant passes strict research gates, run live-market shadow/paper first, then micro-live with hard daily loss and kill-switch limits before scaling.",
        }
    elif baseline_return > 0.0 and severe_return < 0.0:
        next_candidate = {
            "name": "HURST_MTF_COST_ROBUST_V3",
            "scope": "Keep cooldown; reduce turnover and require enough expected move/volatility cushion to survive severe cost stress before any entry.",
            "live_validation": "Use live-market paper/shadow to compare theoretical fills with realistic maker/taker/slippage before any micro-live deployment.",
        }
    else:
        next_candidate = {
            "name": "LEAVE_HURST_MTF_FAMILY",
            "scope": "If both baseline and severe are negative and cooldown leak is not the driver, stop spending Hurst-MTF engineering time and test a different alpha family.",
            "live_validation": "Do not micro-live this family unless a new variant first passes strict research gates.",
        }
    primary_findings = [
        "Hard-stop losses are the main structural leak.",
        "Trailing-stop winners are strong enough to preserve; the issue is failed-entry control, not absence of winners.",
    ]
    if cooldown_leak < -1000.0:
        primary_findings.append("Immediate reentries after losing hard_stop/time_stop/regime_exit are negative and should be tested as a cooldown variant.")
    else:
        primary_findings.append("Losing-exit reentry is no longer the dominant leak after cooldown.")
    if baseline_return > 0.0 and severe_return < 0.0:
        primary_findings.append("Baseline is positive but severe cost stress is negative, so the remaining issue is cost/turnover fragility.")
    elif baseline_return < 0.0:
        primary_findings.append("Baseline is also negative, so the result is not only caused by severe cost stress.")
    if next_candidate["name"] == "LEAVE_HURST_MTF_FAMILY":
        primary_findings.append("This family should not be promoted to micro-live; switch to a different alpha family unless a future independent candidate passes strict research gates.")
    else:
        primary_findings.append("Live market validation remains mandatory, but only after paper/shadow and micro-live gates are explicit.")

    return {
        "status": "diagnostic_only",
        "primary_findings": primary_findings,
        "key_numbers": {
            "hard_stop_trades": hard_stop.get("trades", 0),
            "hard_stop_pnl": hard_stop.get("pnl", 0.0),
            "trailing_stop_trades": trailing_stop.get("trades", 0),
            "trailing_stop_pnl": trailing_stop.get("pnl", 0.0),
            "baseline_compound_return_pct": baseline_return,
            "severe_compound_return_pct": severe_return,
            **cooldown_numbers,
            "selected_next_candidate": next_candidate["name"],
        },
        "scenario_compounds": scenarios,
        "by_exit_reason": by_exit_reason,
        "by_side": by_side,
        "by_symbol": by_symbol,
        "by_period": by_period,
        "by_side_exit_reason": by_side_exit,
        "reentry_diagnostics": reentries,
        "top_winners": top_trades(trades, winners=True),
        "top_losers": top_trades(trades, winners=False),
        "next_candidate": next_candidate,
    }


def _table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows._"
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(col, "")).replace("|", "\\|") for col in columns) + " |")
    return "\n".join(out)


def write_markdown(report: dict[str, Any], path: str | Path) -> None:
    path_text = str(path).upper()
    if "COST_ROBUST_V3" in path_text:
        title = "Hurst MTF Cost-Robust V3 Diagnostics - 2026-05-05"
    elif "COOLDOWN_V2" in path_text:
        title = "Hurst MTF Cooldown V2 Diagnostics - 2026-05-05"
    else:
        title = "Hurst MTF Trade Diagnostics - 2026-05-05"
    lines = [
        f"# {title}",
        "",
        "Status: diagnostic-only. This does not enable paper, testnet, or live execution.",
        "",
        "## Primary Findings",
        "",
    ]
    lines.extend(f"- {item}" for item in report["primary_findings"])
    lines.extend(
        [
            "",
            "## Key Numbers",
            "",
            _table([report["key_numbers"]], list(report["key_numbers"].keys())),
            "",
            "## Scenario Compounds",
            "",
            _table(report["scenario_compounds"], ["scenario", "folds", "positive_folds", "compound_return_pct", "worst_fold_pct", "best_fold_pct"]),
            "",
            "## Exit Reason",
            "",
            _table(report["by_exit_reason"], ["exit_reason", "trades", "pnl", "avg_pnl", "win_rate", "profit_factor"]),
            "",
            "## Side",
            "",
            _table(report["by_side"], ["side", "trades", "pnl", "avg_pnl", "win_rate", "profit_factor"]),
            "",
            "## Reentry Diagnostics",
            "",
            _table(report["reentry_diagnostics"]["all_reentries"], ["gap_hours_lte", "trades", "pnl", "avg_pnl", "win_rate"]),
            "",
            "## After Losing Exit Reentries",
            "",
            _table(report["reentry_diagnostics"]["after_losing_exits"], ["prev_reason", "side", "trades", "pnl", "avg_pnl", "win_rate", "profit_factor"]),
            "",
            "## After Winning Trailing Reentries",
            "",
            _table(report["reentry_diagnostics"]["after_winning_trailing"], ["side", "trades", "pnl", "avg_pnl", "win_rate", "profit_factor"]),
            "",
            "## Worst Symbols",
            "",
            _table(report["by_symbol"], ["symbol", "trades", "pnl", "avg_pnl", "win_rate", "profit_factor"]),
            "",
            "## Worst Periods",
            "",
            _table(report["by_period"], ["period", "trades", "pnl", "avg_pnl", "win_rate", "profit_factor"]),
            "",
            "## Top Winners",
            "",
            _table(report["top_winners"], ["period", "symbol", "side", "entry_time", "exit_time", "exit_reason", "pnl", "bars_held", "reached_1r"]),
            "",
            "## Top Losers",
            "",
            _table(report["top_losers"], ["period", "symbol", "side", "entry_time", "exit_time", "exit_reason", "pnl", "bars_held", "reached_1r"]),
            "",
            "## Next Candidate",
            "",
            _table([report["next_candidate"]], ["name", "scope", "live_validation"]),
        ]
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose Hurst-MTF trade losses and pick the next variant.")
    parser.add_argument("--trades", default=DEFAULT_TRADES)
    parser.add_argument("--results", default=DEFAULT_RESULTS)
    parser.add_argument("--family-limit-reached", action="store_true", help="Mark this as the last planned Hurst-MTF variant if diagnostics remain weak.")
    parser.add_argument("--json-out", default="hurst_mtf_trade_diagnostics.json")
    parser.add_argument("--md-out", default=DEFAULT_MD)
    args = parser.parse_args()

    trades = pd.read_csv(args.trades) if Path(args.trades).exists() else pd.DataFrame()
    results = pd.read_csv(args.results) if Path(args.results).exists() else pd.DataFrame()
    report = build_diagnostics(trades, results, family_limit_reached=args.family_limit_reached)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(risk_metrics.rounded_nested(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.md_out:
        write_markdown(report, args.md_out)
    print(json.dumps(risk_metrics.rounded_nested(report["key_numbers"]), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
