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
    timeframe: str | None = None,
) -> dict[str, Any]:
    timeframe = timeframe or config.TIMEFRAME
    report: dict[str, Any] = {
        "timeframe": timeframe,
        "start_balance": config.CAPITAL_USDT,
        "equity_metrics": {},
        "multiple_testing": {},
    }

    equity_file = Path(equity_path)
    if equity_file.exists() and equity_file.stat().st_size > 0:
        equity = pd.read_csv(equity_file)
        report["equity_metrics"] = risk_metrics.rounded_metrics(
            risk_metrics.equity_metrics(
                equity,
                start_balance=config.CAPITAL_USDT,
                timeframe=timeframe,
            )
        )
        report["equity_source"] = str(equity_file)
    else:
        report["equity_source"] = ""
        report["equity_warning"] = "equity_file_missing"

    sweep_file = Path(sweep_path)
    if sweep_file.exists() and sweep_file.stat().st_size > 0:
        sweep = pd.read_csv(sweep_file)
        report["multiple_testing"] = risk_metrics.candidate_sweep_multiple_testing_summary(sweep)
        report["sweep_source"] = str(sweep_file)
    else:
        report["sweep_source"] = ""
        report["sweep_warning"] = "sweep_file_missing"

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build risk-adjusted and multiple-testing report.")
    parser.add_argument("--equity", default="portfolio_equity.csv")
    parser.add_argument("--sweep", default="portfolio_candidate_sweep_results.csv")
    parser.add_argument("--timeframe", default=config.TIMEFRAME)
    parser.add_argument("--out", default="risk_adjusted_report.json")
    args = parser.parse_args()

    report = build_report(equity_path=args.equity, sweep_path=args.sweep, timeframe=args.timeframe)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
