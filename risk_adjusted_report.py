from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

import config
import risk_metrics


def build_report(
    *,
    equity_path: str = "portfolio_equity.csv",
    sweep_path: str = "portfolio_candidate_sweep_results.csv",
    walk_forward_path: str = "portfolio_param_walk_forward_results.csv",
    timeframe: str | None = None,
) -> dict[str, Any]:
    timeframe = timeframe or config.TIMEFRAME
    report: dict[str, Any] = {
        "timeframe": timeframe,
        "start_balance": config.CAPITAL_USDT,
        "equity_metrics": {},
        "multiple_testing": {},
        "overfit_controls": {},
    }

    raw_equity_metrics: dict[str, float] = {}
    equity_years: float | None = None
    equity_file = Path(equity_path)
    if equity_file.exists() and equity_file.stat().st_size > 0:
        equity = pd.read_csv(equity_file)
        raw_equity_metrics = risk_metrics.equity_metrics(
            equity,
            start_balance=config.CAPITAL_USDT,
            timeframe=timeframe,
        )
        report["equity_metrics"] = risk_metrics.rounded_metrics(raw_equity_metrics)
        returns_count = max(len(equity) - 1, 0)
        if returns_count > 0:
            equity_years = max(
                returns_count / risk_metrics.periods_per_year(timeframe),
                1.0 / 365.0,
            )
        report["equity_source"] = str(equity_file)
    else:
        report["equity_source"] = ""
        report["equity_warning"] = "equity_file_missing"

    sweep_test_count: int | None = None
    sweep_file = Path(sweep_path)
    if sweep_file.exists() and sweep_file.stat().st_size > 0:
        sweep = pd.read_csv(sweep_file)
        mt = risk_metrics.candidate_sweep_multiple_testing_summary(sweep)
        sweep_test_count = int(mt["test_count"])
        report["multiple_testing"] = mt
        report["sweep_source"] = str(sweep_file)
    else:
        report["sweep_source"] = ""
        report["sweep_warning"] = "sweep_file_missing"

    if raw_equity_metrics and equity_years and sweep_test_count:
        report["overfit_controls"]["sharpe_haircut"] = risk_metrics.rounded_nested(
            risk_metrics.multiple_testing_sharpe_haircut(
                sharpe=raw_equity_metrics["sharpe"],
                years=equity_years,
                test_count=sweep_test_count,
            )
        )

    wf_file = Path(walk_forward_path)
    if wf_file.exists() and wf_file.stat().st_size > 0:
        wf = pd.read_csv(wf_file)
        report["overfit_controls"]["walk_forward_degradation"] = risk_metrics.rounded_nested(
            risk_metrics.walk_forward_overfit_summary(wf)
        )
        report["walk_forward_source"] = str(wf_file)
    else:
        report["walk_forward_source"] = ""
        report["walk_forward_warning"] = "walk_forward_file_missing"

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build risk-adjusted and multiple-testing report.")
    parser.add_argument("--equity", default="portfolio_equity.csv")
    parser.add_argument("--sweep", default="portfolio_candidate_sweep_results.csv")
    parser.add_argument("--walk-forward", default="portfolio_param_walk_forward_results.csv")
    parser.add_argument("--timeframe", default=config.TIMEFRAME)
    parser.add_argument("--out", default="risk_adjusted_report.json")
    args = parser.parse_args()

    report = build_report(
        equity_path=args.equity,
        sweep_path=args.sweep,
        walk_forward_path=args.walk_forward,
        timeframe=args.timeframe,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
