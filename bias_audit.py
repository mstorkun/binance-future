"""
Indicator stability audit for lookahead/recursive drift.

It recomputes indicators on rolling prefixes and compares the latest comparable
row against the same timestamp from the full calculation.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable

import pandas as pd

import config
import indicators as ind


DEFAULT_COLUMNS = (
    "atr",
    "rsi",
    "adx",
    "donchian_high",
    "donchian_low",
    "donchian_exit_high",
    "donchian_exit_low",
    "volume_ma",
    "regime",
    "pattern_score_long",
    "pattern_score_short",
    "pattern_bias",
)


@dataclass(frozen=True)
class AuditIssue:
    timestamp: pd.Timestamp
    column: str
    full_value: object
    prefix_value: object
    diff: float | None


def _equal(a, b, tolerance: float) -> tuple[bool, float | None]:
    if pd.isna(a) and pd.isna(b):
        return True, None
    try:
        fa = float(a)
        fb = float(b)
    except (TypeError, ValueError):
        return str(a) == str(b), None
    diff = abs(fa - fb)
    return diff <= tolerance, diff


def audit_indicator_stability(
    raw_df: pd.DataFrame,
    *,
    add_features: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    columns: tuple[str, ...] = DEFAULT_COLUMNS,
    min_prefix: int | None = None,
    sample_step: int = 24,
    compare_row_offset: int = -1,
    tolerance: float = 1e-9,
) -> list[AuditIssue]:
    if len(raw_df) < 5:
        return []

    feature_fn = add_features or ind.add_indicators
    full = feature_fn(raw_df.copy())
    start = min_prefix or max(int(getattr(config, "WARMUP_BARS", 250)), 5)
    start = min(start, len(raw_df) - 1)
    sample_step = max(1, int(sample_step))

    issues: list[AuditIssue] = []
    for end in range(start, len(raw_df) + 1, sample_step):
        prefix = feature_fn(raw_df.iloc[:end].copy())
        if len(prefix) < abs(compare_row_offset):
            continue
        ts = prefix.index[compare_row_offset]
        if ts not in full.index:
            continue
        for col in columns:
            if col not in prefix.columns or col not in full.columns:
                continue
            ok, diff = _equal(full.loc[ts, col], prefix.loc[ts, col], tolerance)
            if not ok:
                issues.append(AuditIssue(ts, col, full.loc[ts, col], prefix.loc[ts, col], diff))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit indicator stability against lookahead/recursive drift.")
    parser.add_argument("--symbol", default=config.SYMBOL)
    parser.add_argument("--timeframe", default=config.TIMEFRAME)
    parser.add_argument("--years", type=int, default=1)
    parser.add_argument("--sample-step", type=int, default=24)
    parser.add_argument("--compare-row-offset", type=int, default=-1)
    parser.add_argument("--fail-on-issue", action="store_true")
    args = parser.parse_args()

    from backtest import _fetch_paginated

    old_symbol = config.SYMBOL
    try:
        config.SYMBOL = args.symbol
        raw = _fetch_paginated(args.timeframe, args.years)
    finally:
        config.SYMBOL = old_symbol

    issues = audit_indicator_stability(
        raw,
        sample_step=args.sample_step,
        compare_row_offset=args.compare_row_offset,
    )
    if not issues:
        print("bias audit: OK - no indicator drift detected")
        return 0

    print(f"bias audit: {len(issues)} issue(s)")
    for issue in issues[:50]:
        print(
            f"{issue.timestamp} {issue.column}: "
            f"full={issue.full_value} prefix={issue.prefix_value} diff={issue.diff}"
        )
    if len(issues) > 50:
        print(f"... {len(issues) - 50} more")
    return 1 if args.fail_on_issue else 0


if __name__ == "__main__":
    raise SystemExit(main())
