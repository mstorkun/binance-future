from __future__ import annotations

import argparse
import contextlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

import config
import paper_report
import paper_runtime


WINDOWS = {
    "daily": pd.Timedelta(days=1),
    "weekly": pd.Timedelta(days=7),
}


@contextlib.contextmanager
def runtime_for_tag(tag: str) -> Iterator[None]:
    if not tag or tag == "default":
        yield
    else:
        with paper_runtime.temporary_paper_runtime(tag=tag):
            yield


def build_dashboard(tags: list[str] | None = None) -> dict[str, Any]:
    tags = tags or ["default", "shadow_2h"]
    return {
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "runs": [build_run_report(tag) for tag in tags],
    }


def build_run_report(tag: str) -> dict[str, Any]:
    with runtime_for_tag(tag):
        base = paper_report.build_report(decision_limit=200)
        decisions = _read_csv(getattr(config, "PAPER_DECISIONS_CSV", "paper_decisions.csv"))
        trades = _read_csv(getattr(config, "PAPER_TRADES_CSV", "paper_trades.csv"))
        errors = _read_csv(getattr(config, "PAPER_ERRORS_CSV", "paper_errors.csv"))

    return {
        "tag": tag or "default",
        "runtime": base["runtime"],
        "heartbeat": base["heartbeat"],
        "open_positions": base["open_positions"],
        "warnings": base["warnings"],
        "windows": {
            name: summarize_window(decisions, trades, errors, window)
            for name, window in WINDOWS.items()
        },
    }


def summarize_window(
    decisions: pd.DataFrame,
    trades: pd.DataFrame,
    errors: pd.DataFrame,
    window: pd.Timedelta,
    *,
    now: pd.Timestamp | None = None,
) -> dict[str, Any]:
    now = now or pd.Timestamp.now(tz="UTC")
    start = now - window
    decision_rows = _filter_since(decisions, "run_at_utc", start)
    trade_rows = _filter_since(trades, "closed_at_utc", start)
    error_rows = _filter_since(errors, "run_at_utc", start)

    action_counts = _counts(decision_rows, "action")
    skip_counts = _counts(decision_rows, "skipped_reason")
    pnls = _numeric_list(trade_rows, "pnl")
    wins = sum(1 for pnl in pnls if pnl > 0)
    losses = sum(1 for pnl in pnls if pnl < 0)
    return {
        "start_utc": start.isoformat(),
        "decision_rows": int(len(decision_rows)),
        "actions": action_counts,
        "skips": skip_counts,
        "trades": int(len(pnls)),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(wins / len(pnls) * 100.0, 4) if pnls else 0.0,
        "total_pnl": round(sum(pnls), 6) if pnls else 0.0,
        "avg_pnl": round(sum(pnls) / len(pnls), 6) if pnls else 0.0,
        "best_pnl": round(max(pnls), 6) if pnls else 0.0,
        "worst_pnl": round(min(pnls), 6) if pnls else 0.0,
        "errors": int(len(error_rows)),
    }


def _read_csv(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(p)


def _filter_since(df: pd.DataFrame, column: str, start: pd.Timestamp) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return pd.DataFrame()
    ts = pd.to_datetime(df[column], errors="coerce", utc=True)
    return df.loc[ts >= start].copy()


def _counts(df: pd.DataFrame, column: str) -> dict[str, int]:
    if df.empty or column not in df.columns:
        return {}
    values = []
    for value in df[column].dropna():
        text = str(value).strip()
        if text and text.lower() != "nan":
            values.append(text)
    return dict(Counter(values))


def _numeric_list(df: pd.DataFrame, column: str) -> list[float]:
    if df.empty or column not in df.columns:
        return []
    return [float(value) for value in pd.to_numeric(df[column], errors="coerce").dropna().tolist()]


def print_text(report: dict[str, Any]) -> None:
    print("=== PAPER DECISION REPORT ===")
    for run in report["runs"]:
        hb = run["heartbeat"]
        rt = run["runtime"]
        print(
            f"\n[{run['tag']}]",
            f"timeframe={rt.get('timeframe')}",
            f"equity={hb.get('equity')}",
            f"wallet={hb.get('wallet')}",
            f"open={hb.get('open_positions')}",
            f"age_min={hb.get('age_minutes')}",
        )
        for name, window in run["windows"].items():
            print(
                f"  {name}:",
                f"decisions={window['decision_rows']}",
                f"actions={window['actions']}",
                f"skips={window['skips']}",
                f"trades={window['trades']}",
                f"pnl={window['total_pnl']}",
                f"win_rate={window['win_rate_pct']}%",
                f"errors={window['errors']}",
            )
        if run["warnings"]:
            print("  warnings:", "; ".join(run["warnings"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare paper decision quality across runs.")
    parser.add_argument("--tags", nargs="*", default=["default", "shadow_2h"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_dashboard(args.tags)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
