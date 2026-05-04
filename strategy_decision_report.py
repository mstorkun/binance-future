from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    file = Path(path)
    if not file.exists() or file.stat().st_size == 0:
        return {}
    return json.loads(file.read_text(encoding="utf-8"))


def strategy_verdict(
    *,
    risk_adjusted: dict[str, Any],
    pbo: dict[str, Any],
    candle_wf: dict[str, Any],
    funding_poc: dict[str, Any] | None = None,
    cross_exchange: dict[str, Any] | None = None,
) -> dict[str, Any]:
    funding_poc = funding_poc or {}
    cross_exchange = cross_exchange or {}
    overfit = risk_adjusted.get("overfit_controls", {})
    sharpe_haircut = overfit.get("sharpe_haircut", {})
    degradation = overfit.get("walk_forward_degradation", {})
    candle_delta = float(candle_wf.get("delta_total_pnl", 0.0) or 0.0)
    reduced = int(candle_wf.get("reduced_overlay_trades", 0) or 0)
    funding_passes = funding_poc.get("passing_symbols")
    cross_exchange_passes = cross_exchange.get("passing_pairs")

    positives: list[str] = []
    negatives: list[str] = []

    if pbo and float(pbo.get("pbo", 1.0)) < 0.2:
        positives.append("full_pbo_matrix_positive")
    if degradation.get("positive_test_folds") == degradation.get("folds") and degradation.get("folds"):
        positives.append("walk_forward_all_positive")

    if sharpe_haircut and not bool(sharpe_haircut.get("passes_zero_edge_after_haircut", True)):
        negatives.append("deflated_sharpe_proxy_negative")
    if int(degradation.get("severe_degradation_folds", 0) or 0) > 0:
        negatives.append("severe_train_test_degradation")
    if candle_delta <= 0.0 and reduced == 0:
        negatives.append("trend_candle_overlay_no_activation_case")
    if funding_passes == 0:
        negatives.append("predictive_funding_poc_zero_pass")
    if cross_exchange_passes == 0:
        negatives.append("cross_exchange_basis_zero_pass")

    if "deflated_sharpe_proxy_negative" in negatives or "trend_candle_overlay_no_activation_case" in negatives:
        decision = "benchmark_only"
    else:
        decision = "continue_research"

    return {
        "decision": decision,
        "live_allowed": False,
        "paper_change_allowed": False,
        "positives": positives,
        "negatives": negatives,
        "next_research_lane": "none_executor_ready",
        "plain_english": (
            "Keep Donchian as a benchmark/research line, not an active live-money strategy. "
            "Do not promote trend/candle/correlation overlays because the true entry-time "
            "walk-forward produced no activation case. Do not build a funding executor unless "
            "a stricter future PoC or cross-exchange basis scan clears OOS fold stability and cost gates."
        ),
    }


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


def build_report(
    *,
    risk_adjusted_path: str = "risk_adjusted_report.json",
    pbo_path: str = "pbo_report.json",
    candle_wf_path: str = "trend_candle_entry_walk_forward.json",
    funding_poc_path: str = "funding_predictability_report.json",
    cross_exchange_path: str = "cross_exchange_basis_report.json",
    carry_doc: str = "docs/CARRY_RESEARCH_2026_05_04.md",
    funding_poc_doc: str = "docs/FUNDING_PREDICTABILITY_2026_05_04.md",
    cross_exchange_doc: str = "docs/CROSS_EXCHANGE_BASIS_2026_05_04.md",
    holdout_doc: str = "docs/PORTFOLIO_HOLDOUT.md",
) -> dict[str, Any]:
    risk_adjusted = load_json(risk_adjusted_path)
    pbo = load_json(pbo_path)
    candle_wf = load_json(candle_wf_path)
    funding_payload = load_json(funding_poc_path)
    funding_rows = funding_payload.get("summary", []) if funding_payload else []
    funding_poc = {
        "symbols_scanned": len(funding_rows),
        "passing_symbols": sum(1 for row in funding_rows if row.get("ok")) if funding_rows else None,
        "fold_rows": len(funding_payload.get("folds", [])) if funding_payload else 0,
        "source": funding_poc_doc,
    }
    cross_payload = load_json(cross_exchange_path)
    cross_rows = cross_payload.get("summary", []) if cross_payload else []
    cross_exchange = {
        "pair_rows": len(cross_rows),
        "pair_rows_with_folds": sum(1 for row in cross_rows if int(row.get("folds", 0) or 0) > 0) if cross_rows else 0,
        "passing_pairs": sum(1 for row in cross_rows if row.get("ok")) if cross_rows else None,
        "fold_rows": len(cross_payload.get("folds", [])) if cross_payload else 0,
        "source": cross_exchange_doc,
    }
    verdict = strategy_verdict(
        risk_adjusted=risk_adjusted,
        pbo=pbo,
        candle_wf=candle_wf,
        funding_poc=funding_poc,
        cross_exchange=cross_exchange,
    )
    equity_metrics = risk_adjusted.get("equity_metrics", {})
    sharpe_haircut = risk_adjusted.get("overfit_controls", {}).get("sharpe_haircut", {})
    degradation = risk_adjusted.get("overfit_controls", {}).get("walk_forward_degradation", {})
    return {
        "verdict": verdict,
        "donchian_baseline": {
            "final_equity": equity_metrics.get("final_equity"),
            "total_return_pct": equity_metrics.get("total_return_pct"),
            "cagr_pct": equity_metrics.get("cagr_pct"),
            "sharpe": equity_metrics.get("sharpe"),
            "max_dd_pct": equity_metrics.get("max_dd_pct"),
            "deflated_sharpe_proxy": sharpe_haircut.get("deflated_sharpe_proxy"),
            "passes_zero_edge_after_haircut": sharpe_haircut.get("passes_zero_edge_after_haircut"),
            "positive_test_folds": degradation.get("positive_test_folds"),
            "severe_degradation_folds": degradation.get("severe_degradation_folds"),
        },
        "pbo": {
            "pbo": pbo.get("pbo"),
            "folds": pbo.get("folds"),
            "avg_oos_rank_pct": pbo.get("avg_oos_rank_pct"),
            "median_oos_rank_pct": pbo.get("median_oos_rank_pct"),
        },
        "trend_candle_entry_wf": {
            "baseline_oos_trades": candle_wf.get("baseline_oos", {}).get("trades"),
            "baseline_oos_pnl": candle_wf.get("baseline_oos", {}).get("total_pnl"),
            "overlay_oos_pnl": candle_wf.get("overlay_oos", {}).get("total_pnl"),
            "delta_total_pnl": candle_wf.get("delta_total_pnl"),
            "reduced_overlay_trades": candle_wf.get("reduced_overlay_trades"),
        },
        "carry_research": {
            "summary": "simple_binance_spot_perp_carry_zero_pass",
            "source": carry_doc,
        },
        "funding_predictability_poc": funding_poc,
        "cross_exchange_basis_poc": cross_exchange,
        "holdout": {
            "summary": "final_500_bar_holdout_positive_but_not_live_approval",
            "source": holdout_doc,
        },
    }


def write_markdown(report: dict[str, Any], path: str | Path) -> None:
    verdict = report["verdict"]
    baseline = report["donchian_baseline"]
    pbo = report["pbo"]
    candle = report["trend_candle_entry_wf"]
    funding = report["funding_predictability_poc"]
    cross = report["cross_exchange_basis_poc"]
    lines = [
        "# Strategy Decision - 2026-05-04",
        "",
        "This is a research decision note, not investment advice and not live",
        "approval.",
        "",
        "## Decision",
        "",
        f"- Verdict: `{verdict['decision']}`",
        "- Keep live trading blocked.",
        "- Keep Donchian as a benchmark/research line only.",
        "- Do not activate trend/candle/correlation reducers in paper/testnet.",
        "- Do not build a funding or cross-exchange basis executor from current PoCs.",
        "",
        "## Evidence",
        "",
        markdown_table(
            [
                {"metric": "final_equity", "value": baseline.get("final_equity")},
                {"metric": "total_return_pct", "value": baseline.get("total_return_pct")},
                {"metric": "sharpe", "value": baseline.get("sharpe")},
                {"metric": "deflated_sharpe_proxy", "value": baseline.get("deflated_sharpe_proxy")},
                {"metric": "passes_zero_edge_after_haircut", "value": baseline.get("passes_zero_edge_after_haircut")},
                {"metric": "positive_test_folds", "value": baseline.get("positive_test_folds")},
                {"metric": "severe_degradation_folds", "value": baseline.get("severe_degradation_folds")},
                {"metric": "full_matrix_pbo", "value": pbo.get("pbo")},
                {"metric": "pbo_avg_oos_rank_pct", "value": pbo.get("avg_oos_rank_pct")},
                {"metric": "trend_candle_oos_delta_pnl", "value": candle.get("delta_total_pnl")},
                {"metric": "trend_candle_reduced_trades", "value": candle.get("reduced_overlay_trades")},
                {"metric": "funding_poc_symbols_scanned", "value": funding.get("symbols_scanned")},
                {"metric": "funding_poc_passing_symbols", "value": funding.get("passing_symbols")},
                {"metric": "funding_poc_fold_rows", "value": funding.get("fold_rows")},
                {"metric": "cross_exchange_pair_rows", "value": cross.get("pair_rows")},
                {"metric": "cross_exchange_pair_rows_with_folds", "value": cross.get("pair_rows_with_folds")},
                {"metric": "cross_exchange_passing_pairs", "value": cross.get("passing_pairs")},
                {"metric": "cross_exchange_fold_rows", "value": cross.get("fold_rows")},
            ],
            ["metric", "value"],
        ),
        "",
        "## Interpretation",
        "",
        "The Donchian portfolio remains useful as a benchmark because PBO and",
        "selected walk-forward evidence are not garbage. It is still not an active",
        "alpha decision because the conservative Sharpe haircut/DSR proxy fails,",
        "train/test degradation is severe, simple Binance carry produced zero",
        "passing candidates, the predictive-funding PoC produced zero strict",
        "passing symbols, cross-exchange basis produced zero passing pairs,",
        "and the true entry-time trend/candle reducer found no",
        "train-proven bad setup to exploit.",
        "",
        "## Next Step",
        "",
        "Do not spend more engineering time on live execution gates until a new",
        "alpha path has evidence after costs and walk-forward validation. The",
        "remaining research choices are stricter data acquisition/model variants",
        "or keeping Donchian only as a benchmark.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the strategy keep/kill decision report.")
    parser.add_argument("--risk-adjusted", default="risk_adjusted_report.json")
    parser.add_argument("--pbo", default="pbo_report.json")
    parser.add_argument("--candle-wf", default="trend_candle_entry_walk_forward.json")
    parser.add_argument("--funding-poc", default="funding_predictability_report.json")
    parser.add_argument("--cross-exchange", default="cross_exchange_basis_report.json")
    parser.add_argument("--json-out", default="strategy_decision_report.json")
    parser.add_argument("--md-out", default="docs/STRATEGY_DECISION_2026_05_04.md")
    args = parser.parse_args()
    report = build_report(
        risk_adjusted_path=args.risk_adjusted,
        pbo_path=args.pbo,
        candle_wf_path=args.candle_wf,
        funding_poc_path=args.funding_poc,
        cross_exchange_path=args.cross_exchange,
    )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.md_out:
        write_markdown(report, args.md_out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
