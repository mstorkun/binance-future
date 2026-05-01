from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

import bias_audit
import config


def issue_to_dict(issue: bias_audit.AuditIssue) -> dict[str, Any]:
    return {
        "timestamp": pd.Timestamp(issue.timestamp).isoformat(),
        "column": issue.column,
        "full_value": _json_safe(issue.full_value),
        "prefix_value": _json_safe(issue.prefix_value),
        "diff": issue.diff,
    }


def build_symbol_report(
    *,
    symbol: str,
    timeframe: str,
    years: int,
    sample_step: int,
    compare_row_offset: int = -1,
) -> dict[str, Any]:
    from backtest import _fetch_paginated

    old_symbol = config.SYMBOL
    try:
        config.SYMBOL = symbol
        raw = _fetch_paginated(timeframe, years)
    finally:
        config.SYMBOL = old_symbol

    issues = bias_audit.audit_indicator_stability(
        raw,
        sample_step=sample_step,
        compare_row_offset=compare_row_offset,
    )
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "years": years,
        "sample_step": sample_step,
        "compare_row_offset": compare_row_offset,
        "rows": int(len(raw)),
        "columns_checked": list(bias_audit.DEFAULT_COLUMNS),
        "issue_count": int(len(issues)),
        "status": "ok" if not issues else "issues",
        "issues_preview": [issue_to_dict(issue) for issue in issues[:25]],
    }


def build_report(
    *,
    symbols: list[str],
    timeframe: str,
    years: int,
    sample_step: int,
    compare_row_offset: int = -1,
) -> dict[str, Any]:
    symbol_reports = [
        build_symbol_report(
            symbol=symbol,
            timeframe=timeframe,
            years=years,
            sample_step=sample_step,
            compare_row_offset=compare_row_offset,
        )
        for symbol in symbols
    ]
    return {
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "symbols": symbols,
        "timeframe": timeframe,
        "years": years,
        "sample_step": sample_step,
        "compare_row_offset": compare_row_offset,
        "total_issue_count": int(sum(row["issue_count"] for row in symbol_reports)),
        "status": "ok" if all(row["status"] == "ok" for row in symbol_reports) else "issues",
        "results": symbol_reports,
    }


def _json_safe(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a reproducible bias-audit summary report.")
    parser.add_argument("--symbols", nargs="*", default=list(getattr(config, "SYMBOLS", [config.SYMBOL])))
    parser.add_argument("--timeframe", default=config.TIMEFRAME)
    parser.add_argument("--years", type=int, default=1)
    parser.add_argument("--sample-step", type=int, default=96)
    parser.add_argument("--compare-row-offset", type=int, default=-1)
    parser.add_argument("--out", default="docs/BIAS_AUDIT_REPORT_2026_05_01.json")
    parser.add_argument("--fail-on-issue", action="store_true")
    args = parser.parse_args()

    report = build_report(
        symbols=args.symbols,
        timeframe=args.timeframe,
        years=args.years,
        sample_step=args.sample_step,
        compare_row_offset=args.compare_row_offset,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    if args.fail_on_issue and report["total_issue_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
